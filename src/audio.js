/**
 * BGM プレイヤー（WebAudio）
 *
 * なぜ <audio> ではなく WebAudio か:
 *
 *  1. <audio> はストリーミング経路に依存する。実測では loadstart の直後に
 *     stalled が出て readyState=0 のまま固まり、HTTP リクエストがサーバーに
 *     一度も到達しない環境があった（53KB の SE でも同様）。
 *     同じページで fetch + decodeAudioData は 90ms で完走する。
 *  2. ゲーム用途では WebAudio の方が本来適切:
 *     - AudioBufferSourceNode.loop はサンプル単位で継ぎ目なくループする
 *       （<audio loop> はループ境界に無音が入りうる）
 *     - SE をサンプル精度でスケジュールできる
 *     - GainNode でクリックノイズの出ないフェードができる
 *
 * 音源のフォーマット:
 *   TRACKS には拡張子を書かず、再生時にブラウザの対応状況で選ぶ。
 *   - .ogg (Opus) … 最軽量。Chrome / Firefox / Edge。
 *   - .m4a (AAC)  … Safari / iOS 用のフォールバック。
 *   wav マスターから `python tools/encode_audio.py` で生成する。
 */

/** 拡張子なしのベースパス。実際の拡張子は pickFormats() が決める */
export const TRACKS = {
  title:   "assets/BGM/Title",
  opening: "assets/BGM/Opening",
};

/**
 * 再生できるフォーマットを優先順に返す。
 *
 * decodeAudioData は事前に対応可否を教えてくれないので、<audio> の
 * canPlayType で判定する（デコーダは両者で共通）。判定を外した場合に
 * 備えて、実際の読み込みでは先頭から順に試して失敗したら次へ回す。
 */
function pickFormats() {
  const probe = document.createElement("audio");
  const opus = probe.canPlayType('audio/ogg; codecs="opus"');
  // Safari は ogg/Opus を再生できないので AAC を先に試す
  return opus ? ["ogg", "m4a"] : ["m4a", "ogg"];
}

const MUTE_KEY = "mtfil.muted";

function loadMuted() {
  try {
    return localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

function saveMuted(v) {
  try {
    localStorage.setItem(MUTE_KEY, v ? "1" : "0");
  } catch {
    /* 保存できなくても再生は続ける */
  }
}

/**
 * @param {object}   opts
 * @param {number}   opts.volume      通常時の音量 (0..1)
 * @param {number}   opts.fadeIn      フェードイン時間 ms
 * @param {Function} opts.onBlocked   AudioContext が suspended のままのとき
 * @param {Function} opts.onPlaying   実際に鳴り始めたとき
 */
export function createBgm({ volume = 0.55, fadeIn = 1800, onBlocked, onPlaying } = {}) {
  const buffers = new Map();
  const formats = pickFormats();

  let ctx = null;
  let gain = null;
  let source = null;
  let baseVolume = volume;
  let muted = loadMuted();
  let pendingTrack = null;
  let unlockArmed = false;

  const UNLOCK_EVENTS = ["pointerdown", "keydown", "touchstart"];

  function ensureCtx() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      ctx = new AC();
      gain = ctx.createGain();
      gain.gain.value = 0;
      gain.connect(ctx.destination);
    }
    return ctx;
  }

  /** 対応フォーマットを順に試して、最初に読めたものを返す */
  /**
   * AudioContext が running になるのを待つ。
   *
   * 注意: 自動再生がブロックされている間、Chrome の ctx.resume() は reject せず
   * Promise を pending のまま放置する。await すると判定処理に到達できないので、
   * resume() は投げっぱなしにして statechange を時間制限つきで待つ。
   */
  function waitForRunning(ms) {
    if (ctx.state === "running") return Promise.resolve(true);
    return new Promise((resolve) => {
      let settled = false;
      const finish = (v) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        ctx.removeEventListener("statechange", onChange);
        resolve(v);
      };
      const onChange = () => {
        if (ctx.state === "running") finish(true);
      };
      const timer = setTimeout(() => finish(ctx.state === "running"), ms);
      ctx.addEventListener("statechange", onChange);
    });
  }

  /** 同期的に呼ぶこと（ユーザー操作のコンテキストを失わないため） */
  function tryResume() {
    if (ctx.state !== "running") ctx.resume().catch(() => {});
  }

  async function loadBuffer(base) {
    if (buffers.has(base)) return buffers.get(base);

    const errors = [];
    for (const ext of formats) {
      const url = `${base}.${ext}`;
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const bytes = await res.arrayBuffer();
        const buf = await ensureCtx().decodeAudioData(bytes);
        buffers.set(base, buf);
        return buf;
      } catch (err) {
        errors.push(`${ext}: ${err?.message ?? err}`);
      }
    }
    throw new Error(`no playable format for ${base} (${errors.join(" / ")})`);
  }

  /** GainNode を滑らかに動かす。setValueAtTime を挟まないとプチノイズが出る */
  function rampGain(to, ms) {
    const now = ctx.currentTime;
    const target = muted ? 0 : Math.min(1, Math.max(0, to));
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    if (ms <= 0) gain.gain.setValueAtTime(target, now);
    else gain.gain.linearRampToValueAtTime(target, now + ms / 1000);
  }

  function stopSource() {
    if (!source) return;
    try {
      source.stop();
    } catch {
      /* 既に停止済み */
    }
    source.disconnect();
    source = null;
  }

  function startSource(buf) {
    stopSource();
    source = ctx.createBufferSource();
    source.buffer = buf;
    source.loop = true;
    source.connect(gain);
    source.start(0);
  }

  function disarmUnlock() {
    unlockArmed = false;
    UNLOCK_EVENTS.forEach((e) => window.removeEventListener(e, onInteract));
  }

  async function onInteract() {
    // ユーザー操作のコンテキスト内で同期的に resume を呼ぶ必要がある
    tryResume();
    if (!(await waitForRunning(1000))) return; // まだ許可されない。次の操作を待つ

    disarmUnlock();
    if (pendingTrack) {
      startSource(pendingTrack);
      pendingTrack = null;
    }
    rampGain(baseVolume, fadeIn);
    onPlaying?.();
  }

  function armUnlock() {
    if (unlockArmed) return;
    unlockArmed = true;
    UNLOCK_EVENTS.forEach((e) => window.addEventListener(e, onInteract));
  }

  return {
    /** 共有用。SE も同じ AudioContext に載せると遅延が揃う */
    get context() {
      return ctx;
    },

    /** トラックを読み込んで再生を試みる */
    async play(name, { volume: v = baseVolume } = {}) {
      const base = TRACKS[name];
      if (!base) throw new Error(`unknown track: ${name}`);
      baseVolume = v;

      ensureCtx();

      let buf;
      try {
        buf = await loadBuffer(base);
      } catch (err) {
        console.error("[bgm] failed to load", base, err);
        return;
      }

      // 自動再生ポリシーで suspended のまま起動することがある
      tryResume();

      if (!(await waitForRunning(600))) {
        console.warn("[bgm] AudioContext is suspended — waiting for a user gesture");
        pendingTrack = buf;
        onBlocked?.();
        armUnlock();
        return;
      }

      startSource(buf);
      rampGain(baseVolume, fadeIn);
      onPlaying?.();
    },

    /** フェードアウトして停止（シーン遷移用） */
    async stop(ms = 800) {
      if (!ctx || !source) return;
      rampGain(0, ms);
      await new Promise((r) => setTimeout(r, ms));
      stopSource();
    },

    /** @returns {boolean} 変更後のミュート状態 */
    toggleMute() {
      muted = !muted;
      saveMuted(muted);
      if (ctx) rampGain(baseVolume, 120);
      return muted;
    },

    get muted() {
      return muted;
    },
  };
}
