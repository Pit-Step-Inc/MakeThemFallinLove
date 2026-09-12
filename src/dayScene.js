/**
 * 日付切り替えシーン（「1日目」）
 *
 * 参照: assets/reference_image/DayChange.png
 *
 * 中央に何日目かを出し、左右で Martin と Catherine を歩かせる。
 * 歩きは 2 人とも 24F=1.00秒・毎分120歩で作られていて歩調が揃うので、
 * 同時に走らせても位相がぶつからない（develop/Martin/README.md 参照）。
 *
 * 素材の読み込みは初期化時に先に始める。表示の瞬間に fetch すると
 * 1 フレーム分キャンバスが空で出てちらつくため。
 * 読み込みに失敗しても日付の表示だけは出す（進行を止めない）。
 */

import { t } from "./i18n.js";
import { loadClip, createSpriteAnim } from "./spriteAnim.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx        audio.js の createSfx()
 * @param {Function}  opts.onAdvance  () => void  画面が押されたら呼ぶ
 */
export function initDayScene({ lang, sfx, onAdvance }) {
  const scene = document.getElementById("scene-day");
  const label = document.getElementById("dayLabel");
  const hint  = document.getElementById("dayHint");

  /** @type {ReturnType<typeof createSpriteAnim>[]} */
  const anims = [];

  let uiLang = lang;
  let day = 1;
  let visible = false;
  let advanced = false;

  const walkers = [
    { id: "martinWalk",    character: "Martin",    clip: "martin_walk" },
    { id: "catherineWalk", character: "Catherine", clip: "catherine_walk" },
  ];

  const ready = Promise.all(
    walkers.map(async ({ id, character, clip }) => {
      const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById(id));
      try {
        const data = await loadClip(character, clip);
        const anim = createSpriteAnim(canvas, data);
        anims.push(anim);
        // 読み込みが表示より後ろにずれ込んだ場合はここで追い付かせる
        if (visible) play(anim);
      } catch (err) {
        console.error("[day] failed to load", clip, err);
        canvas.hidden = true;
      }
    })
  );

  function play(anim) {
    if (reduceMotion?.matches) anim.pose();
    else anim.start();
  }

  function applyStrings() {
    const s = t(uiLang);
    label.textContent = s.day(day);
    hint.textContent = s.dayHint;
  }

  /**
   * 画面のどこを押しても次へ進む。
   * 二重発火（連打・クリックとキーの同時）を止めるので、進むのは一度だけ。
   */
  function advance() {
    if (!visible || advanced) return;
    advanced = true;

    sfx?.play("dayStart");
    onAdvance?.();
  }

  function onKeyDown(e) {
    if (!visible || e.isComposing) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      advance();
    }
  }

  // 右下の BGM トグルは .scene の外（.stage 直下）にあるので、
  // ここで拾うクリックには混ざらない
  scene.addEventListener("click", advance);
  window.addEventListener("keydown", onKeyDown);

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
      applyStrings();
    },

    /**
     * 何日目かを差し込んでシーンを起こす。showScene() の前に呼ぶこと。
     * @param {number} n 1 から
     */
    prepare(n) {
      day = n;
      advanced = false;
      applyStrings();
      // 押した瞬間に鳴ってほしいので先に読んでおく
      sfx?.preload("dayStart");
      return ready;
    },

    /** シーンが表示されたあとに呼ぶ */
    start() {
      visible = true;
      anims.forEach(play);
    },

    /** シーンを抜けるときに呼ぶ。裏で rAF を回し続けない */
    stop() {
      visible = false;
      anims.forEach((a) => a.stop());
    },
  };
}
