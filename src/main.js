/**
 * Make Them Fall (in love) — エントリポイント
 *
 * BGM を立ち上げ、シーンを順に繋ぐ。
 * 各シーンのロジックは title.js / nickname.js 側にある。
 */

import { createBgm } from "./audio.js";
import { showScene } from "./scenes.js";
import { initTitle, loadLang } from "./title.js";
import { initNickname } from "./nickname.js";
import { t } from "./i18n.js";

const stage    = document.getElementById("stage");
const soundBtn = document.getElementById("soundToggle");

/** 初期言語: 前回選んだもの → ブラウザの言語 → en */
let uiLang = loadLang() ?? (navigator.language?.startsWith("ja") ? "ja" : "en");

/* ---------------------------------------------------------------
   BGM（全シーン共通）
   --------------------------------------------------------------- */
const bgm = createBgm({
  volume: 0.55,
  fadeIn: 1800,
  // 自動再生がブロックされても画面には出さない。
  // audio.js 側が最初のクリック / キー入力を待って無言で再生を開始する。
  onBlocked: undefined,
  onPlaying: undefined,
});

function syncSoundBtn() {
  soundBtn.setAttribute("aria-pressed", String(bgm.muted));
}

soundBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  bgm.toggleMute();
  syncSoundBtn();
});

window.addEventListener("keydown", (e) => {
  // 入力欄で "m" を打てなくならないように、テキスト入力中は無視する
  const el = document.activeElement;
  if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;

  if (e.key === "m" || e.key === "M") {
    bgm.toggleMute();
    syncSoundBtn();
  }
});

syncSoundBtn();
bgm.play("title");

/* ---------------------------------------------------------------
   シーンの配線
   --------------------------------------------------------------- */
const nickname = initNickname({
  lang: uiLang,
  onDone: onNicknameEntered,
  onBack: async () => {
    await showScene("scene-title");
    title.focus();
  },
});

const title = initTitle({
  lang: uiLang,
  onDone: async (lang) => {
    uiLang = lang;
    document.documentElement.lang = lang;
    stage.dispatchEvent(
      new CustomEvent("game:languageselected", { detail: { lang }, bubbles: true })
    );

    // 言語が決まったのでニックネーム画面の文言を入れ直す
    nickname.setLang(lang);

    await showScene("scene-nickname");
    nickname.focus();
  },
});

function onNicknameEntered(name) {
  stage.dispatchEvent(
    new CustomEvent("game:nicknameentered", { detail: { nickname: name }, bubbles: true })
  );

  // TODO: オープニングへ遷移する。BGM の差し替えはこの形で書ける:
  //   await bgm.stop(800);
  //   bgm.play("opening");
  document.getElementById("nicknameHint").textContent = t(uiLang).notImplemented(name);
  console.log("[game] nickname:", name);
}

showScene("scene-title");
