/**
 * 会話の画面（二人の立ち絵 + 吹き出し）
 *
 * 参照: assets/reference_image/opening_001.png, opening_002.png
 *
 * 背景の上に立ち絵と吹き出しを重ねるだけの画面。台詞は
 * [{ who, text, emotion? }, ...] を上から順に流す。**2箇所で使う**:
 *   - 各日の冒頭（台本は i18n の openingScripts・背景は街の1枚絵。どちらも main.js が渡す）
 *   - 生成された次の展開（台本も背景も OpenAI から来る／tools/story.py）
 *
 * 吹き出しは話者ごとに1つずつ固定位置にあり、**直前の発言が残る**。
 * 参照画像の2枚目が Martin「や、やぁ」と Catherine「で？これからどうするの？」を
 * 同時に映しているのがこの形。位置も大きさも台詞の長さでは変えない。
 *
 * 口パクの既定は martin_talk03 / catherine_talk01。どちらも10コマ前後あって
 * 口以外は全コマ同一画素なので、立ち絵として置いたまま回しても顔がぶれない
 * （assets/blender/develop/Martin/README.md 参照）。コマ0が閉じた口なので、
 * 喋っていないあいだは pose() でそこに戻す。
 *
 * 台詞に emotion（joy / anger / sadness / pleasure / surprised）が付いていれば、
 * その表情のクリップに差し替えて喋らせる。
 *
 * **要素が無いキャラは居ないものとして扱う。** ラストシーンは Catherine だけなので、
 * そこに Martin のキャンバスや吹き出しを置かずに済む。
 */

import { loadClip, createSpriteAnim } from "./spriteAnim.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/** 1文字あたりの表示間隔 ms */
const TYPE_MS = 45;

/**
 * emotion → クリップ名。
 * Martin の surprised だけ 10コマ版（surprised02）を使う。6コマ版は
 * コマの縦横比が 0.500 で他の表情（0.68〜0.69）と違い、同じ枠に入れると横に潰れる。
 */
const EMOTION_CLIPS = {
  martin: {
    joy: "martin_joy", anger: "martin_anger", sadness: "martin_sadness",
    pleasure: "martin_pleasure", surprised: "martin_surprised02",
  },
  catherine: {
    joy: "catherine_joy", anger: "catherine_anger", sadness: "catherine_sadness",
    pleasure: "catherine_pleasure", surprised: "catherine_surprised",
  },
};

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx      audio.js の createSfx()
 * @param {string}    opts.sceneId  この会話を置く <section> の id
 * @param {string}    opts.prefix   要素 id の接頭辞（openingMartin なら "opening"）
 * @param {boolean}   opts.catherineFromStart Catherine を最初から出しておくか
 * @param {Function}  opts.onDone   最後の台詞のあと、もう一度送られたら呼ぶ
 */
export function initTalkScene({ lang, sfx, sceneId, prefix, catherineFromStart = false, onDone }) {
  const scene = document.getElementById(sceneId);
  const el = (suffix) => document.getElementById(prefix + suffix);
  const backdrop = /** @type {HTMLImageElement|null} */ (el("Backdrop"));

  /** この画面に居るキャラだけを組む。要素が無ければ出番なし */
  const cast = {};
  for (const [who, spec] of Object.entries({
    martin: {
      character: "Martin",
      base: "martin_talk03",
      suffix: "Martin",
      /** 最初から画面に居るか。冒頭の Catherine は合流してから出す */
      onStage: true,
    },
    catherine: {
      character: "Catherine",
      base: "catherine_talk01",
      suffix: "Catherine",
      onStage: catherineFromStart,
    },
  })) {
    const canvas = el(spec.suffix);
    if (!canvas) continue;
    cast[who] = {
      character: spec.character,
      base: spec.base,
      clip: spec.base,
      canvas,
      bubble: el("Bubble" + spec.suffix),
      shown:  el("Shown" + spec.suffix),
      rest:   el("Rest" + spec.suffix),
      // 名札。喋っていなくても出しっぱなしで、立ち絵と一緒に出入りする
      nameTag: el("Name" + spec.suffix),
      onStage: spec.onStage,
      anim: null,
    };
  }
  const everyone = Object.values(cast);

  let uiLang = lang;
  let script = [];
  let index = -1;
  let timer = 0;
  let typing = false;
  let visible = false;
  let finished = false;

  /**
   * その人のクリップを差し替える。同じものなら何もしない。
   * loadClip は読んだものを覚えているので、同じ表情が続いても取りに行かない。
   */
  async function useClip(c, name) {
    if (c.clip === name && c.anim) return;
    try {
      const clip = await loadClip(c.character, name);
      c.anim?.stop();
      c.clip = name;
      c.anim = createSpriteAnim(c.canvas, clip);
      c.anim.pose();                   // 口を閉じた状態で置いておく
      c.canvas.hidden = false;
    } catch (err) {
      console.error("[talk] failed to load", name, err);
      // 読めなければ元のクリップのまま続ける。画面は止めない
    }
  }

  const ready = Promise.all(everyone.map((c) => useClip(c, c.base)));

  /** 話している人だけ口を動かす */
  function speak(speaker) {
    for (const c of everyone) {
      if (c === speaker && !reduceMotion?.matches) c.anim?.start();
      else c.anim?.pose();
    }
  }

  /** 台詞を一気に出し切る。途中でクリックされたときもここに来る */
  function finishLine() {
    clearInterval(timer);
    timer = 0;
    typing = false;

    const line = script[index];
    const c = line && cast[line.who];
    if (c) {
      c.shown.textContent = line.text;
      c.rest.textContent = "";
    }
    speak(null);
  }

  async function showLine(i) {
    index = i;
    const { who, text, emotion } = script[i];
    const c = cast[who];
    if (!c) {                          // この画面に居ないキャラの台詞。飛ばす
      if (i + 1 < script.length) showLine(i + 1);
      else finishLine();
      return;
    }

    c.bubble.hidden = false;
    if (!c.onStage) {
      c.onStage = true;
      c.canvas.hidden = false;
      if (c.nameTag) c.nameTag.hidden = false;
    }

    // 表情が指定されていればそのクリップへ。無ければ既定の口パクに戻す
    const wanted = EMOTION_CLIPS[who]?.[emotion] ?? c.base;
    await useClip(c, wanted);
    if (index !== i) return;           // 待っているあいだに次へ送られた

    if (reduceMotion?.matches) {
      finishLine();
      return;
    }

    const chars = [...text];
    let n = 0;
    c.shown.textContent = "";
    c.rest.textContent = text;

    speak(c);
    typing = true;
    timer = setInterval(() => {
      // 改行に1コマ使うとそこだけ間延びするので、次の文字まで一緒に送る
      do { n += 1; } while (n < chars.length && chars[n - 1] === "\n");

      c.shown.textContent = chars.slice(0, n).join("");
      c.rest.textContent = chars.slice(n).join("");

      if (n >= chars.length) finishLine();
    }, TYPE_MS);
  }

  /**
   * 送る。表示途中なら最後まで出し、出し切っていれば次の台詞へ。
   * SE は「切り替わった」ときだけで、出し切るだけのときは鳴らさない。
   */
  function advance() {
    if (!visible || !script.length) return;

    if (typing) {
      finishLine();
      return;
    }
    if (index + 1 >= script.length) {
      // 台本の終わり。吹き出しを片付けて Prompt 入力へ渡す。
      // 以降このシーンはクリックにもキーにも反応しない
      if (finished) return;
      finished = true;
      visible = false;
      for (const c of everyone) c.bubble.hidden = true;
      onDone?.();
      return;
    }

    sfx?.play("chatNext");
    showLine(index + 1);
  }

  function onKeyDown(e) {
    if (!visible || e.isComposing) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      advance();
    }
  }

  scene.addEventListener("click", advance);
  window.addEventListener("keydown", onKeyDown);

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
    },

    /**
     * 背景を差し替える。冒頭は日ごとの街、次の展開は生成された1枚。
     * 背景を持たない画面（ラストシーン）では何もしない。
     */
    setBackdrop(src) {
      if (!backdrop) return;
      backdrop.hidden = !src;
      if (src) backdrop.src = src;
    },

    /**
     * 素材を揃えて頭から組み直す。showScene() の前に呼ぶこと。
     * @param {{who: string, text: string, emotion?: string}[]} [lines]
     *        省略すると台詞なし（背景と立ち絵だけ出す）
     */
    prepare(lines) {
      script = lines ?? [];
      index = -1;
      finished = false;
      clearInterval(timer);
      timer = 0;
      typing = false;

      for (const c of everyone) {
        c.bubble.hidden = true;
        c.shown.textContent = "";
        c.rest.textContent = "";
        c.anim?.pose();
      }
      if (cast.catherine) {
        cast.catherine.onStage = catherineFromStart;
        cast.catherine.canvas.hidden = !catherineFromStart;
        if (cast.catherine.nameTag) cast.catherine.nameTag.hidden = !catherineFromStart;
      }

      sfx?.preload("chatNext");
      return ready;
    },

    /** シーンが表示されたあとに呼ぶ */
    start() {
      visible = true;
      if (script.length) showLine(0);
    },

    /** シーンを抜けるときに呼ぶ。裏で rAF とタイマーを回し続けない */
    stop() {
      visible = false;
      clearInterval(timer);
      timer = 0;
      typing = false;
      for (const c of everyone) c.anim?.stop();
    },
  };
}
