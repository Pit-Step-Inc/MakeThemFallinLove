/**
 * Make Them Fall (in love) — エントリポイント
 *
 * BGM を立ち上げ、シーンを順に繋ぐ。
 * 各シーンのロジックは title.js / nickname.js / dayScene.js /
 * openingScene.js 側にある。
 */

import { createBgm, createSfx } from "./audio.js";
import { showScene } from "./scenes.js";
import { initTitle, loadLang } from "./title.js";
import { initNickname } from "./nickname.js";
import { initDayScene } from "./dayScene.js";
import { initOpeningScene } from "./openingScene.js";

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

/* ---------------------------------------------------------------
   SE（決定 / キャンセル）

   BGM と同じ AudioContext に載る。右下のトグルは BGM 専用なので
   SE はミュートの影響を受けない（audio.js の createSfx を参照）。
   --------------------------------------------------------------- */
const sfx = createSfx({ volume: 0.6 });
sfx.preload("confirm", "cancel");

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
const opening = initOpeningScene({ lang: uiLang, sfx });

const dayScene = initDayScene({
  lang: uiLang,
  sfx,
  onAdvance: async () => {
    // BGM を Day から Opening へ。await しないのは Title → Day と同じ理由で、
    // 読み込みとフェードインを待つとそのあいだ画面が止まるため。
    // 入れ替わりの 0.7 秒は day_start_jingle が鳴っているので間は空かない。
    bgm.stop(700)
      .then(() => bgm.play("opening"))
      .catch((err) => console.error("[bgm] failed to switch to opening", err));

    await opening.prepare();
    await showScene("scene-opening");
    dayScene.stop();          // 裏で歩きを回し続けない
    opening.start();
  },
});

const nickname = initNickname({
  lang: uiLang,
  sfx,
  onDone: onNicknameEntered,
  onBack: async () => {
    await showScene("scene-title");
    title.focus();
  },
});

const title = initTitle({
  lang: uiLang,
  sfx,
  onDone: async (lang) => {
    uiLang = lang;
    document.documentElement.lang = lang;
    stage.dispatchEvent(
      new CustomEvent("game:languageselected", { detail: { lang }, bubbles: true })
    );

    // 言語が決まったので以降の画面の文言を入れ直す
    nickname.setLang(lang);
    dayScene.setLang(lang);
    opening.setLang(lang);

    await showScene("scene-nickname");
    nickname.focus();
  },
});

async function onNicknameEntered(name) {
  stage.dispatchEvent(
    new CustomEvent("game:nicknameentered", { detail: { nickname: name }, bubbles: true })
  );
  console.log("[game] nickname:", name);

  // BGM を Title から Day へ差し替える。
  // await しないのは、Day の読み込みとフェードイン（1.8秒）を待つと
  // そのあいだ画面が止まってしまうため。音と絵を並行で走らせる。
  bgm.stop(700)
    .then(() => bgm.play("day"))
    .catch((err) => console.error("[bgm] failed to switch to day", err));

  // 素材の読み込みを待ってから出す。待たずに出すと 1 フレームだけ
  // キャンバスが空になる。失敗しても prepare() は解決するので止まらない。
  await dayScene.prepare(1);
  await showScene("scene-day");
  dayScene.start();
}

showScene("scene-title");
