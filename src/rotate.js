/**
 * 縦向きのときの案内
 *
 * この画面は 16:9 の横長ひとつで出来ているので、縦向きだと細い帯になって
 * 遊べない。**ページ側から端末の回転ロックは外せない**（通常のタブでは
 * screen.orientation.lock() が全画面のときしか許されず、iOS Safari は
 * そもそも持っていない）ので、できるのは次の3つだけ。
 *
 *   1. manifest.webmanifest の "orientation": "landscape"
 *      … ホーム画面に追加して開いた場合は、これで横向きになる
 *   2. 「横画面にする」で全画面 → screen.orientation.lock("landscape")
 *      … Android Chrome ではこれで回る。効かない端末では黙って何もしない
 *   3. 文章で案内する（回転ロックを外してもらう）
 *
 * 縦向きのあいだだけ全面に出し、横になったら自分で引っ込む。
 */

import { t } from "./i18n.js";

/** 全画面と向きの固定が両方できる端末か。できないなら札は出さない */
function canForceLandscape() {
  return Boolean(document.documentElement.requestFullscreen) &&
         Boolean(screen.orientation?.lock);
}

/** @param {{lang: "en"|"ja"}} opts */
export function initRotateNotice({ lang }) {
  const root = document.getElementById("rotateNotice");
  const textEl = document.getElementById("rotateText");
  const hintEl = document.getElementById("rotateHint");
  const btn = /** @type {HTMLButtonElement} */ (document.getElementById("rotateBtn"));
  if (!root) return { setLang() {} };

  let uiLang = lang;

  function applyStrings() {
    const s = t(uiLang);
    textEl.textContent = s.rotateText;
    hintEl.textContent = s.rotateHint;
    btn.textContent = s.rotateBtn;
  }

  /**
   * 縦のあいだだけ出す。**タッチの端末だけ**が相手で、
   * パソコンで窓を縦長にしただけのときは邪魔をしない
   */
  const portrait = window.matchMedia("(orientation: portrait)");
  const coarse = window.matchMedia("(pointer: coarse)");

  function update() {
    const show = portrait.matches && coarse.matches;
    root.hidden = !show;
    btn.hidden = !canForceLandscape();
  }

  btn.addEventListener("click", async () => {
    // 全画面にしないと向きの固定は許されない。どちらも失敗しうるので、
    // 落ちても案内はそのまま出しておく（回転ロックを外してもらう）
    try {
      await document.documentElement.requestFullscreen();
      await screen.orientation.lock("landscape");
    } catch (err) {
      console.warn("[rotate] could not force landscape", err);
    }
  });

  portrait.addEventListener("change", update);
  coarse.addEventListener("change", update);

  applyStrings();
  update();

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
      applyStrings();
    },
  };
}
