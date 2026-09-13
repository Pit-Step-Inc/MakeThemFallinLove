/**
 * 部屋コードの札
 *
 * 部屋に入ったあと、画面の右上に出したままにする。押すとコピーできる。
 *
 * 【コピーは2段構え】
 * navigator.clipboard は **安全なコンテキストでしか生えない**。
 * localhost なら使えるが、スマホから入るときの
 * http://192.168.x.x:5173 では undefined になる。
 * そこで、無ければ昔ながらの execCommand("copy") に落ちる。
 *
 * 【出しっぱなしにしない画面がある】
 * Prompt 入力と切り替え画面は上段が投稿カードで埋まっていて、
 * 右上に置くと重なる。その2つでは hide() して引っ込める。
 */

import { t } from "./i18n.js";

/** 「コピーしました」を出しておく時間 ms */
const COPIED_MS = 1400;

export function createCodeChip({ lang, sfx }) {
  const root  = document.getElementById("codeChip");
  const label = document.getElementById("codeChipLabel");
  const value = document.getElementById("codeChipValue");

  let uiLang = lang;
  let code = "";
  let timer = 0;

  function applyStrings() {
    const s = t(uiLang);
    label.textContent = s.roomCode;
    root.setAttribute("aria-label", s.copyCode);
  }

  /** クリップボードが使えない環境（http の LAN 越しなど）向け */
  function copyFallback(text) {
    const scratch = document.createElement("textarea");
    scratch.value = text;
    // 画面外に置く。display:none だと選択できない
    scratch.setAttribute("readonly", "");
    scratch.style.cssText = "position:absolute;left:-9999px;top:0;opacity:0";
    document.body.append(scratch);
    scratch.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    scratch.remove();
    return ok;
  }

  async function copy() {
    if (!code) return;
    sfx?.play("confirm");

    let ok = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(code);
        ok = true;
      }
    } catch {
      ok = false;
    }
    if (!ok) ok = copyFallback(code);

    label.textContent = t(uiLang)[ok ? "codeCopied" : "codeCopyFailed"];
    root.classList.toggle("is-copied", ok);
    clearTimeout(timer);
    timer = setTimeout(() => {
      root.classList.remove("is-copied");
      applyStrings();
    }, COPIED_MS);
  }

  root.addEventListener("click", copy);
  applyStrings();

  return {
    setLang(l) {
      uiLang = l;
      applyStrings();
    },

    /** 部屋に入ったら呼ぶ。空文字なら札ごと引っ込める */
    setCode(next) {
      code = next ?? "";
      value.textContent = code;
      root.hidden = !code;
    },

    show() {
      if (code) root.hidden = false;
    },

    hide() {
      root.hidden = true;
    },
  };
}
