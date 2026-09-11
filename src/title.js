/**
 * タイトルシーン
 *
 * 言語を選ばせて保存するところまでを担当する。
 * 選ばれた言語は onDone(lang) で呼び出し元へ渡す。
 */

import { t } from "./i18n.js";

const STORAGE_KEY = "mtfil.lang";

/** 決定時フラッシュの長さ。style.css の .btn.is-chosen と揃えること */
const FLASH_MS = 420 * 3;

export function loadLang() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "en" || v === "ja" ? v : null;
  } catch {
    return null;
  }
}

function saveLang(lang) {
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    /* 保存できなくても進行は妨げない */
  }
}

/**
 * @param {object}   opts
 * @param {"en"|"ja"} opts.lang    初期フォーカスに使う言語
 * @param {Function} opts.onDone   (lang) => void
 */
export function initTitle({ lang, onDone }) {
  const scene   = document.getElementById("scene-title");
  const hintEl  = document.getElementById("titleHint");
  const buttons = /** @type {HTMLButtonElement[]} */ ([...scene.querySelectorAll(".btn")]);

  let locked = false;

  hintEl.textContent = t(lang).titleHint;

  let focusIndex = buttons.findIndex((b) => b.dataset.lang === lang);
  if (focusIndex < 0) focusIndex = 0;

  function moveFocus(delta) {
    focusIndex = (focusIndex + delta + buttons.length) % buttons.length;
    buttons[focusIndex].focus();
  }

  function choose(btn) {
    if (locked) return;
    locked = true;

    const chosen = btn.dataset.lang;
    saveLang(chosen);
    hintEl.textContent = t(chosen).titleHint;

    btn.classList.add("is-chosen");
    buttons.forEach((b) => { b.disabled = true; });

    // animationend では待たない。タブが裏に回ると document.timeline が止まり、
    // アニメーションが完走せずイベントが永久に発火しないため
    // （scenes.js の冒頭に同じ理由のメモあり）。
    setTimeout(() => {
      btn.classList.remove("is-chosen");
      buttons.forEach((b) => { b.disabled = false; });
      locked = false;
      onDone(chosen);
    }, FLASH_MS);
  }

  buttons.forEach((btn, i) => {
    btn.addEventListener("click", () => choose(btn));
    btn.addEventListener("pointerenter", () => { focusIndex = i; });
  });

  // シーンが隠れている間はキー操作を拾わない
  window.addEventListener("keydown", (e) => {
    if (scene.hidden || locked) return;

    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      moveFocus(1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      moveFocus(-1);
    } else if (e.key === "Enter" || e.key === " ") {
      // ボタンにフォーカスが無い状態でも決定できるようにする
      if (document.activeElement !== buttons[focusIndex]) {
        e.preventDefault();
        choose(buttons[focusIndex]);
      }
    }
  });

  /** シーンが表示されたあとに呼ぶ */
  return {
    focus() {
      buttons[focusIndex].focus();
    },
  };
}
