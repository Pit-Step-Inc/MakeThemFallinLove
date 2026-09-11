/**
 * ニックネーム入力シーン
 *
 * 7 文字まで。入力が空のあいだは「つぎへ」を押せない。
 */

import { t } from "./i18n.js";

const STORAGE_KEY = "mtfil.nickname";
export const MAX_LENGTH = 7;

export function loadNickname() {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveNickname(name) {
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    /* 保存できなくても進行は妨げない */
  }
}

/**
 * 先頭 MAX_LENGTH 「文字」に切り詰める。
 * maxlength 属性は UTF-16 単位で数えるので、絵文字や結合文字が
 * 2 文字分を消費してしまう。コードポイント単位で数え直す。
 */
function clamp(value) {
  const chars = [...value];
  return chars.length > MAX_LENGTH ? chars.slice(0, MAX_LENGTH).join("") : value;
}

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {Function}  opts.onDone  (nickname) => void
 * @param {Function}  opts.onBack  () => void   言語選択へ戻る
 */
export function initNickname({ lang, onDone, onBack }) {
  const scene   = document.getElementById("scene-nickname");
  const heading = document.getElementById("nameHeading");
  const input   = /** @type {HTMLInputElement} */ (document.getElementById("nameInput"));
  const nextBtn = /** @type {HTMLButtonElement} */ (document.getElementById("nextBtn"));
  const backBtn = /** @type {HTMLButtonElement} */ (document.getElementById("backBtn"));
  const hintEl  = document.getElementById("nicknameHint");

  /** 文言をまとめて差し替える。呼び出し側で個別に書くと更新漏れが出る */
  function applyStrings(l) {
    const s = t(l);
    heading.textContent = s.yourName;
    input.placeholder = s.namePlaceholder;
    nextBtn.textContent = s.next;
    backBtn.textContent = s.back;
    hintEl.textContent = s.nicknameHint;
  }

  applyStrings(lang);
  input.value = loadNickname();

  function syncNext() {
    nextBtn.disabled = input.value.trim().length === 0;
  }

  input.addEventListener("input", () => {
    const clamped = clamp(input.value);
    if (clamped !== input.value) {
      const pos = input.selectionStart;
      input.value = clamped;
      // 切り詰めでカーソルが末尾に飛ばないようにする
      if (pos !== null) input.setSelectionRange(Math.min(pos, clamped.length), Math.min(pos, clamped.length));
    }
    syncNext();
  });

  input.addEventListener("keydown", (e) => {
    // IME 変換中の Enter / Escape は確定・取り消し操作なので拾わない
    if (e.isComposing) return;

    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onBack?.();
    }
  });

  nextBtn.addEventListener("click", submit);
  backBtn.addEventListener("click", () => onBack?.());

  // 入力欄の外にフォーカスがあるときでも Escape で戻れるようにする
  window.addEventListener("keydown", (e) => {
    if (scene.hidden || e.isComposing) return;
    if (e.key === "Escape" && document.activeElement !== input) {
      e.preventDefault();
      onBack?.();
    }
  });

  function submit() {
    const name = input.value.trim();
    if (!name) {
      input.focus();
      return;
    }
    saveNickname(name);
    onDone(name);
  }

  syncNext();

  return {
    /** タイトルで言語が確定したら呼ぶ */
    setLang(l) {
      applyStrings(l);
    },

    /** シーンが表示されたあとに呼ぶ */
    focus() {
      input.focus();
      syncNext();
    },
  };
}
