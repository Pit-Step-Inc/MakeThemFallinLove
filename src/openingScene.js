/**
 * オープニング（渋谷・1日目冒頭の会話）
 *
 * 参照: assets/reference_image/opening_001.png, opening_002.png
 *
 * 背景の上に立ち絵と吹き出しを重ねるだけの画面。台詞は i18n の
 * openingScript（[{ who, text }, ...]）を上から順に流す。
 *
 * 吹き出しは話者ごとに1つずつ固定位置にあり、**直前の発言が残る**。
 * 参照画像の2枚目が Martin「や、やぁ」と Catherine「で？これからどうするの？」を
 * 同時に映しているのがこの形。位置も大きさも台詞の長さでは変えない。
 *
 * 口パクは martin_talk03 / catherine_talk01。どちらも10コマ前後あって
 * 口以外は全コマ同一画素なので、立ち絵として置いたまま回しても顔がぶれない
 * （assets/blender/develop/Martin/README.md 参照）。コマ0が閉じた口なので、
 * 喋っていないあいだは pose() でそこに戻す。
 */

import { t } from "./i18n.js";
import { loadClip, createSpriteAnim } from "./spriteAnim.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/** 1文字あたりの表示間隔 ms */
const TYPE_MS = 45;

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx   audio.js の createSfx()
 */
export function initOpeningScene({ lang, sfx }) {
  const scene = document.getElementById("scene-opening");

  const cast = {
    martin: {
      character: "Martin",
      clip: "martin_talk03",
      canvas: document.getElementById("openingMartin"),
      bubble: document.getElementById("bubbleMartin"),
      shown:  document.getElementById("shownMartin"),
      rest:   document.getElementById("restMartin"),
      /** 最初から画面に居るか。Catherine は合流してから出す */
      onStage: true,
      anim: null,
    },
    catherine: {
      character: "Catherine",
      clip: "catherine_talk01",
      canvas: document.getElementById("openingCatherine"),
      bubble: document.getElementById("bubbleCatherine"),
      shown:  document.getElementById("shownCatherine"),
      rest:   document.getElementById("restCatherine"),
      onStage: false,
      anim: null,
    },
  };
  const everyone = Object.values(cast);

  let uiLang = lang;
  let script = [];
  let index = -1;
  let timer = 0;
  let typing = false;
  let visible = false;

  const ready = Promise.all(
    everyone.map(async (c) => {
      try {
        const clip = await loadClip(c.character, c.clip);
        c.anim = createSpriteAnim(c.canvas, clip);
        c.anim.pose();                 // 口を閉じた状態で置いておく
      } catch (err) {
        console.error("[opening] failed to load", c.clip, err);
        c.canvas.hidden = true;
      }
    })
  );

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

    const { who, text } = script[index];
    cast[who].shown.textContent = text;
    cast[who].rest.textContent = "";
    speak(null);
  }

  function showLine(i) {
    index = i;
    const { who, text } = script[i];
    const c = cast[who];

    c.bubble.hidden = false;
    if (!c.onStage) {
      c.onStage = true;
      c.canvas.hidden = false;
    }

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
    if (index + 1 >= script.length) return;   // この先はまだ無い

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

    /** 素材を揃えて頭から組み直す。showScene() の前に呼ぶこと */
    prepare() {
      script = t(uiLang).openingScript;
      index = -1;
      clearInterval(timer);
      timer = 0;
      typing = false;

      for (const c of everyone) {
        c.bubble.hidden = true;
        c.shown.textContent = "";
        c.rest.textContent = "";
        c.anim?.pose();
      }
      cast.catherine.onStage = false;
      cast.catherine.canvas.hidden = true;

      sfx?.preload("chatNext");
      return ready;
    },

    /** シーンが表示されたあとに呼ぶ */
    start() {
      visible = true;
      showLine(0);
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
