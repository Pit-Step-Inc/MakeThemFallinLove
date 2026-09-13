/**
 * Make Them Fall (in love) — エントリポイント
 *
 * BGM を立ち上げ、シーンを順に繋ぐ。
 * 各シーンのロジックは title.js / nickname.js / dayScene.js /
 * talkScene.js 側にある。
 */

import { createBgm, createSfx } from "./audio.js";
import { showScene } from "./scenes.js";
import { initTitle, loadLang } from "./title.js";
import { initNickname } from "./nickname.js";
import { initDayScene } from "./dayScene.js";
import { initTalkScene } from "./talkScene.js";
import { initPromptScene, TIME_LIMIT } from "./promptScene.js";
import { initSceneChange } from "./sceneChange.js";
import { createRoom } from "./room.js";
import { initRoomScene } from "./roomScene.js";
import { createCodeChip } from "./codeChip.js";
import { createAffection } from "./affection.js";
import { createToaster } from "./toast.js";
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
/* ---------------------------------------------------------------
   部屋（Prompt の共有）

   タイトルで選んだ言語がそのまま部屋になる。ニックネームを決めた時点で
   参加し、同じ部屋に居る人の Prompt とカウントダウンを共有する。
   サーバーが居なければ黙って一人用に落ちる（src/room.js 参照）。
   --------------------------------------------------------------- */
const room = createRoom({ roundSeconds: TIME_LIMIT });
const toaster = createToaster();
const codeChip = createCodeChip({ lang: uiLang, sfx });
const affection = createAffection();

/** いま何日目か。日付画面の行き先を分けるのに使う（サーバーが決める） */
let currentDay = 1;
let allDaysDone = false;

room.onState((state) => {
  if (!state) return;
  // 親密度も日数も部屋が持っている。ここは映すだけ
  affection.setValue(state.affinity ?? 0);
  if (typeof state.day === "number") currentDay = state.day;
  allDaysDone = Boolean(state.allDaysDone);
});

// 誰かが入ってきた / 抜けたを、どの画面に居ても出す
room.onEvent((event) => {
  const s = t(uiLang);
  if (event.type === "join") toaster.show(s.playerJoined(event.name));
  else if (event.type === "leave") toaster.show(s.playerLeft(event.name));
});

const sceneChange = initSceneChange({ lang: uiLang, sfx });

const promptScene = initPromptScene({
  lang: uiLang,
  sfx,
  room,
  // 制限時間が切れたら切り替え画面へ。ここは背景が総取っ替えになるので、
  // 会話→Prompt と違って showScene を通す
  onTimeUp: async () => {
    codeChip.hide();
    await sceneChange.prepare(promptScene.results());
    await showScene("scene-change");
    promptScene.stop();
    opening.stop();
    story.stop();
    sceneChange.start();

    // 渦を回したまま、いちばんいいねが多かった Prompt から次の展開を作らせる。
    // 生成に10秒ほどかかるので、この画面がそのまま待ち時間になる
    await playNextScene();
  },
});

/** ラストシーン。Catherine の独り言だけ（assets/Prompt/003.txt） */
const lastScene = initTalkScene({
  lang: uiLang,
  sfx,
  sceneId: "scene-last",
  prefix: "last",
  catherineFromStart: true,
});

/** 生成された次の展開。背景も台詞も BGM も OpenAI から来る */
const story = initTalkScene({
  lang: uiLang,
  sfx,
  sceneId: "scene-story",
  prefix: "story",
  catherineFromStart: true,
  // 生成された会話を送り終わったら、次の日へ。3日ぶん終わっていれば締めへ
  onDone: () => afterStory(),
});

const opening = initTalkScene({
  lang: uiLang,
  sfx,
  sceneId: "scene-opening",
  prefix: "opening",
  // 会話が終わったら同じ画面のまま Prompt 入力へ。
  // showScene を挟まないのは、背景も立ち絵も動かないのに暗転してしまうため
  onDone: () => startPromptPhase(),
});

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

    sceneChange.stop();
    promptScene.stop();

    if (currentDay > 1) {
      // 2日目からは冒頭の会話を挟まない。前の日に生成された背景に戻して、
      // その上で次の Prompt を書いてもらう
      await story.prepare([]);
      await showScene("scene-story");
      dayScene.stop();
      startPromptPhase();
      return;
    }

    await opening.prepare();
    await showScene("scene-opening");
    dayScene.stop();          // 裏で歩きを回し続けない
    opening.start();
  },
});

const roomScene = initRoomScene({
  lang: uiLang,
  sfx,
  room,
  // 建った / 入れた。コードの札を出して日付画面へ
  onDone: async () => {
    codeChip.setCode(room.code);
    console.log("[game] room:", room.code || "(solo)", room.isHost ? "host" : "client");
    await startDay();
  },
});

const nickname = initNickname({
  lang: uiLang,
  sfx,
  onDone: onNicknameEntered,
  onBack: async () => {
    affection.hide();
    codeChip.setCode("");
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
    roomScene.setLang(lang);
    codeChip.setLang(lang);
    dayScene.setLang(lang);
    opening.setLang(lang);
    story.setLang(lang);
    lastScene.setLang(lang);
    promptScene.setLang(lang);
    sceneChange.setLang(lang);

    await showScene("scene-nickname");
    nickname.focus();
  },
});

async function onNicknameEntered(name) {
  stage.dispatchEvent(
    new CustomEvent("game:nicknameentered", { detail: { nickname: name }, bubbles: true })
  );
  console.log("[game] nickname:", name);

  // 名前が決まったら部屋を選ぶ。ここで建てるか、コードで入るか
  roomScene.useName(() => name);
  await showScene("scene-room");
  roomScene.focus();
}

/**
 * 日付画面を出す。1日目は本編の入り口、2日目以降は次の日のはじまり。
 * ここを抜けた先は dayScene の onAdvance が日によって振り分ける。
 */
async function startDay() {
  // BGM を Title から Day へ差し替える。
  // await しないのは、Day の読み込みとフェードイン（1.8秒）を待つと
  // そのあいだ画面が止まってしまうため。音と絵を並行で走らせる。
  bgm.stop(700)
    .then(() => bgm.play("day"))
    .catch((err) => console.error("[bgm] failed to switch to day", err));

  // 日付画面は二人が歩いているだけの画面。ゲージを出すと Catherine に重なる
  affection.hide();

  // 素材の読み込みを待ってから出す。待たずに出すと 1 フレームだけ
  // キャンバスが空になる。失敗しても prepare() は解決するので止まらない。
  await dayScene.prepare(currentDay);
  await showScene("scene-day");
  dayScene.start();
}

/**
 * 生成された会話を送り終わったあと。
 * まだ日が残っていれば次の日へ、3日ぶん終わっていれば締めのシーンへ。
 */
async function afterStory() {
  if (!allDaysDone) {
    story.stop();
    await startNextDay();
    return;
  }
  await playFinale();
}

/** 次の日の日付画面へ。BGM はタイトルの流れに戻さず Day に戻す */
async function startNextDay() {
  bgm.stop(700)
    .then(() => bgm.play("day"))
    .catch((err) => console.error("[bgm] failed to switch to day", err));

  codeChip.show();
  affection.hide();          // 日付画面では Catherine に重なるので引っ込める
  await dayScene.prepare(currentDay);
  await showScene("scene-day");
  dayScene.start();
}

/**
 * 締め。これまでの会話と親密度から Catherine の独り言を作らせて流す。
 * 作るのは部屋につき1回だけで、2人目以降は同じものを受け取る。
 */
async function playFinale() {
  codeChip.hide();
  affection.show();

  await sceneChange.prepare(promptScene.results());
  await showScene("scene-change");
  story.stop();
  sceneChange.start();
  sceneChange.setStatus(t(uiLang).wrappingUp);

  let state = await room.finale();
  for (let i = 0; i < 90 && state?.finale?.status === "working"; i += 1) {
    await new Promise((r) => setTimeout(r, 1000));
    state = await room.state();
  }

  const made = state?.finale;
  if (!made || made.status !== "ready" || !made.lines?.length) {
    console.error("[finale] not ready:", made?.error ?? made?.status);
    sceneChange.setStatus(t(uiLang).generateFailed);
    return;
  }

  bgm.stop(700)
    .then(() => bgm.play("Bittersweet"))
    .catch((err) => console.error("[bgm] failed to switch for the finale", err));

  await lastScene.prepare(made.lines);
  await showScene("scene-last");
  sceneChange.stop();
  sceneChange.setStatus(null);
  lastScene.start();
}

/**
 * Prompt 入力フェーズに入る。
 *
 * 1回目は冒頭の会話のあと、2回目からは生成された会話のあと。
 * Prompt の画面はシーンの外に置いてあるので、**そのときの背景の上にそのまま重なる**
 * （1回目は渋谷、2回目からは前の回で生成された背景）。
 *
 * 新しい回として組み直すかどうかはサーバーが決める（tools/rooms.py の _is_stale）。
 * こちらは ready を打つだけでよい。
 */
function startPromptPhase() {
  // 上段がカードで埋まるので、コードの札はここで引っ込める
  codeChip.hide();
  affection.show();
  promptScene.prepare();
  promptScene.start();
}

/**
 * 次の展開を作らせて、出来たら会話として流す。
 *
 * 作るのは部屋につき1回だけで、2人目以降は同じものを受け取る（tools/rooms.py）。
 * ここでは出来上がりを待って、背景・台詞・BGM を差し替える。
 */
async function playNextScene() {
  sceneChange.setStatus(t(uiLang).generating);

  let state = await room.story();
  // 出来上がるまで待つ。渦と SE は回ったままなので、待っている感じにはならない
  for (let i = 0; i < 120 && state?.story?.status === "working"; i += 1) {
    await new Promise((r) => setTimeout(r, 1000));
    state = await room.state();
  }

  const made = state?.story;
  if (!made || made.status !== "ready" || !made.lines?.length) {
    console.error("[story] not ready:", made?.error ?? made?.status);
    sceneChange.setStatus(t(uiLang).generateFailed);
    return;
  }
  console.log("[story]", made.winner, "/ bgm:", made.bgm, "/ affinity:", made.affinity);

  // BGM は生成側が選んだもの。知らない名前なら今のまま鳴らし続ける
  if (made.bgm) {
    bgm.stop(700)
      .then(() => bgm.play(made.bgm))
      .catch((err) => console.error("[bgm] failed to switch to", made.bgm, err));
  }

  await story.prepare(made.lines);
  story.setBackdrop(made.image);

  await showScene("scene-story");
  sceneChange.stop();
  sceneChange.setStatus(null);
  affection.show();
  story.start();

  // ゲージが動いただけだと気づきにくいので、増減も一度出す
  if (made.affinity) {
    const s = t(uiLang);
    toaster.show(made.affinity > 0 ? s.affinityUp(made.affinity) : s.affinityDown(-made.affinity));
  }
}

showScene("scene-title");
