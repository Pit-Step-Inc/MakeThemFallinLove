/**
 * シーン切り替え画面
 *
 * 参照: assets/reference_image/scene_change.png
 *
 * Prompt 入力の制限時間が切れたらここへ来る。背景は develop/scene_change の
 * ワープ、上段はそれまでの投稿、中央は **いちばんいいねが多かった Prompt**。
 *
 * 背景は 32コマ / 1.333秒 で、本来は「画面を切り替える一回きりの覆い」
 * （develop/scene_change/README.md）。ここでは次のシーンがまだ無いので
 * そのままループさせている。先頭と末尾はアルファ 0 なので、
 * つなぎ目は見えない。**途中の F20-F22 は全面が白飛びする**ので、
 * 白い閃光を出したくない場合は下の LOOP_RANGE を [3, 15]（渦だけ）に絞る。
 */

import { t } from "./i18n.js";
import { loadFrameClip, createFrameAnim } from "./spriteAnim.js";
import { buildPromptCard, fillPromptCard } from "./promptCard.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/** 背景として回すコマの範囲（両端を含む）。null なら全コマ */
const LOOP_RANGE = null;

/** 動きを減らす設定のときに出す1コマ。参照画像と同じ渦のあたり */
const STILL_FRAME = 10;

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx   audio.js の createSfx()
 */
export function initSceneChange({ lang, sfx }) {
  const fxEl      = /** @type {HTMLImageElement} */ (document.getElementById("changeFx"));
  const listEl    = document.getElementById("changeCards");
  const headingEl = document.getElementById("changeHeading");
  const heroEl    = document.getElementById("changeHero");

  let uiLang = lang;
  let anim = null;
  let visible = false;

  const ready = loadFrameClip("scene_change", "scene_change")
    .then((clip) => {
      if (LOOP_RANGE) {
        const [from, to] = LOOP_RANGE;
        clip = { ...clip, frames: clip.frames.filter((f) => f >= from && f <= to) };
      }
      anim = createFrameAnim(fxEl, clip);
      anim.pose(STILL_FRAME);
      if (visible) play();
    })
    .catch((err) => {
      console.error("[sceneChange] failed to load scene_change", err);
      fxEl.hidden = true;
    });

  function play() {
    if (!anim) return;
    // 全面が白く飛ぶコマがあるので、動きを減らす設定では渦の1コマで止める
    if (reduceMotion?.matches) anim.pose(STILL_FRAME);
    else anim.start();
  }

  /** @param {{author: string, text: string, likes: number}[]} results いいね順 */
  function render(results) {
    headingEl.textContent = t(uiLang).nextUp;

    listEl.replaceChildren();
    for (const r of results) {
      const els = buildPromptCard({ interactive: false });
      fillPromptCard(els, r);
      listEl.append(els.slot);
    }

    // 中央はいちばんいいねが多かった1件。1件も無ければ出さない
    heroEl.replaceChildren();
    const top = results[0];
    heroEl.hidden = !top;
    if (!top) return;

    const els = buildPromptCard({ interactive: false });
    els.slot.classList.add("prompt-card-slot--hero");
    fillPromptCard(els, top);
    heroEl.append(els.slot);
  }

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
      headingEl.textContent = t(uiLang).nextUp;
    },

    /** 生成の進み具合を見出しに出す。null で元の「次の展開」に戻す */
    setStatus(text) {
      headingEl.textContent = text ?? t(uiLang).nextUp;
    },

    /**
     * 中央のお題だけを差し替える。
     *
     * **投稿が1件も無い回**のためにある。ランダムイベントと、誰も Prompt を
     * 出さなかった回は、お題を AI が考える（tools/rooms.py の _run_event /
     * _run_story）。決まるのが渦を出したあとなので、prepare() を通さずに
     * ここだけ後から埋める（prepare() は見出しも上段も組み直してしまう）。
     *
     * @param {{author: string, text: string, likes: number}|null} result
     */
    showHero(result) {
      heroEl.replaceChildren();
      heroEl.hidden = !result;
      if (!result) return;

      const els = buildPromptCard({ interactive: false });
      els.slot.classList.add("prompt-card-slot--hero");
      fillPromptCard(els, result);
      heroEl.append(els.slot);
    },

    /**
     * 出す前に呼ぶ。素材の読み込みを待つ
     * @param {{author: string, text: string, likes: number}[]} results promptScene.results()
     */
    prepare(results) {
      render(results);
      sfx?.preload("sceneChange");
      return ready;
    },

    /** シーンが表示されたあとに呼ぶ */
    start() {
      visible = true;
      play();
      sfx?.loop("sceneChange");
    },

    /** 抜けるときに呼ぶ。裏で rAF と SE を回し続けない */
    stop() {
      visible = false;
      anim?.stop();
      sfx?.stopLoop("sceneChange");
    },
  };
}
