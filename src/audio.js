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
  day:     "assets/BGM/Day",
  // エンディング。素材のファイル名が EndrRoll なのでそれに合わせてある
  endRoll: "assets/BGM/EndrRoll",

  // 生成された展開で選ばれる5曲。名前は assets/Prompt/002.txt の選択肢と
  // そろえてある（tools/story.py の BGM_CHOICES）
  Excited:     "assets/BGM/Excited",
  Funny:       "assets/BGM/Funny",
  Romantic:    "assets/BGM/Romantic",
  Tense:       "assets/BGM/Tense",
  Bittersweet: "assets/BGM/Bittersweet",
};

/** 効果音。BGM と同じく拡張子なし */
export const SE = {
  confirm:  "assets/SE/retro_button_confirm",
  cancel:   "assets/SE/retro_button_cancel",
  dayStart: "assets/SE/day_start_jingle",
  chatNext: "assets/SE/chat_next_chun",
  sceneChange: "assets/SE/scene_transition_fuwan_fuwa_chakiin",
  affinity: "assets/SE/cute_like_pi_se",
  // 0.44 秒の短いループ素材。鳴らしっぱなしにするなら sfx.loop("siren")
  siren: "assets/SE/rising_siren_loop_sharp",
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

/* ---------------------------------------------------------------
   AudioContext とデコード済みバッファは BGM と SE で共有する。

   context を分けると出力の遅延が揃わないうえ、ブラウザには同時に持てる
   AudioContext の数に上限がある。バッファも共通の置き場にしておけば、
   同じ素材を BGM と SE の両方から読んでも一度しか取りに行かない。
   --------------------------------------------------------------- */

let sharedCtx = null;

/** AudioContext を1つだけ作って使い回す */
export function audioContext() {
  if (!sharedCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    sharedCtx = new AC();
  }
  return sharedCtx;
}

/** 同期的に呼ぶこと（ユーザー操作のコンテキストを失わないため） */
function tryResume() {
  const ctx = audioContext();
  if (ctx.state !== "running") ctx.resume().catch(() => {});
}

/** base（拡張子なし）→ Promise<AudioBuffer> */
const buffers = new Map();
let formats = null;

/** 対応フォーマットを順に試して、最初に読めたものを返す */
async function fetchBuffer(base) {
  formats ??= pickFormats();

  const errors = [];
  for (const ext of formats) {
    const url = `${base}.${ext}`;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const bytes = await res.arrayBuffer();
      return await audioContext().decodeAudioData(bytes);
    } catch (err) {
      errors.push(`${ext}: ${err?.message ?? err}`);
    }
  }
  throw new Error(`no playable format for ${base} (${errors.join(" / ")})`);
}

/**
 * バッファを読む。バッファそのものではなく Promise をキャッシュするので、
 * 同じ素材を同時に2箇所から呼んでも fetch は1回で済む。
 */
function loadBuffer(base) {
  let pending = buffers.get(base);
  if (!pending) {
    pending = fetchBuffer(base);
    // 失敗を握ったままにすると二度と読み直せなくなる
    pending.catch(() => buffers.delete(base));
    buffers.set(base, pending);
  }
  return pending;
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
      ctx = audioContext();
      gain = ctx.createGain();
      gain.gain.value = 0;
      gain.connect(ctx.destination);
    }
    return ctx;
  }

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

/**
 * SE プレイヤー
 *
 * BGM と同じ AudioContext・同じバッファ置き場に載せる（audioContext の
 * コメント参照）。
 *
 * BGM のミュートには連動しない。画面右下のトグルは「BGM のオン / オフ」
 * であって、SE まで止めるとボタンの手応えが消えるため。
 * だからこのトグル自体には SE を付けていない（消音したのに音が鳴る、
 * という一番紛らわしい組み合わせになる）。
 */
export function createSfx({ volume = 0.6 } = {}) {
  let gain = null;

  /** 鳴らしっぱなしの音。名前 → { source, stopped } */
  const looping = new Map();

  function ensureGain() {
    if (!gain) {
      const ctx = audioContext();
      gain = ctx.createGain();
      gain.gain.value = volume;
      gain.connect(ctx.destination);
    }
    return gain;
  }

  return {
    /**
     * 先に読んでデコードまで済ませておく。
     * 最初の1回だけ鳴らない、を防ぐためのもの。
     */
    preload(...names) {
      ensureGain();
      return Promise.all(
        names.map((n) =>
          loadBuffer(SE[n]).catch((err) => console.error("[sfx] failed to load", n, err))
        )
      );
    },

    /**
     * 鳴らす。押した瞬間に返せるよう待たせない。
     * 読み込みが終わっていなければ、終わり次第そのまま鳴る。
     */
    play(name) {
      const base = SE[name];
      if (!base) {
        console.error("[sfx] unknown sfx:", name);
        return;
      }

      // クリックのハンドラから同期的に呼ぶ必要がある
      tryResume();

      const out = ensureGain();
      loadBuffer(base)
        .then((buf) => {
          // BufferSource は使い捨て。鳴らすたびに作る
          const src = audioContext().createBufferSource();
          src.buffer = buf;
          src.connect(out);
          src.start(0);
        })
        .catch((err) => console.error("[sfx]", name, err));
    },

    /**
     * 切れ目なく鳴らし続ける。同じ名前を二度呼んでも1本しか鳴らない。
     * 止めるのは stopLoop(name)。
     */
    loop(name) {
      const base = SE[name];
      if (!base) {
        console.error("[sfx] unknown sfx:", name);
        return;
      }
      if (looping.has(name)) return;

      tryResume();

      // 読み込みを待つあいだに stopLoop されることがあるので、
      // 先に席を取っておいて、戻ってきたときに取り消されていないか見る
      const entry = { source: null, stopped: false };
      looping.set(name, entry);

      const out = ensureGain();
      loadBuffer(base)
        .then((buf) => {
          if (entry.stopped) return;
          const src = audioContext().createBufferSource();
          src.buffer = buf;
          src.loop = true;
          src.connect(out);
          src.start(0);
          entry.source = src;
        })
        .catch((err) => {
          looping.delete(name);
          console.error("[sfx]", name, err);
        });
    },

    /** loop() で鳴らしているものを止める */
    stopLoop(name) {
      const entry = looping.get(name);
      if (!entry) return;
      entry.stopped = true;
      looping.delete(name);
      if (!entry.source) return;
      try {
        entry.source.stop();
      } catch {
        /* 既に停止済み */
      }
      entry.source.disconnect();
    },
  };
}
