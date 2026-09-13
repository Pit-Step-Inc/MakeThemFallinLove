/**
 * エンディング
 *
 * 参照: assets/reference_image/Memory_001.png, Memory_002.png（回想）
 *       assets/reference_image/Ending_001.png（TOP PLAYERS）
 *       assets/reference_image/Ending_002.png（The End）
 *
 * Catherine の独り言が終わったら、ここで締める。順番は
 *
 *   1. 回想   … 3日ぶんの思い出。生成された背景の上に二人と、その日の会話の
 *                最後のやりとり、それと**選ばれた Prompt の札**を重ねる
 *   2. TOP PLAYERS … もらったいいねの合計が多かった3人
 *   3. スタッフロール
 *   4. The End
 *
 * **2〜4 は同じ画面**で、ロゴと歩く二人は出しっぱなしのまま真ん中だけ
 * 入れ替える（参照画像の2枚が同じ構図なので、切り替えると絵が跳ねる）。
 *
 * BGM は 1 に入るところで EndRoll に差し替えて、最後まで流しっぱなし。
 *
 * 回想は放っておいても進むが、押せば先へ送れる。スタッフロールは
 * CSS のアニメーションが終わったところで The End に移る。
 */

import { t } from "./i18n.js";
import { loadClip, createSpriteAnim } from "./spriteAnim.js";
import { buildPromptCard, fillPromptCard } from "./promptCard.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/** 回想1枚を映しておく時間 ms */
const MEMORY_MS = 6000;

/** スタッフロールが流れ切るまで ms（style.css の credits-roll と揃える） */
const CREDITS_MS = 32000;

/** The End を出してから操作を受けるまで ms。押しっぱなしで飛ばされないように */
const END_SETTLE_MS = 1200;

/**
 * スタッフロール。名前と道具なので訳さない（i18n には置かない）。
 * 見出しは太字、それ以外は「役割: 名前」の1行。
 */
const CREDITS = [
  { heading: "Production Credits" },
  { role: "Producer",        name: "Jun Misaki" },
  { role: "Game Design",     name: "Jun Misaki / Shunya Abe" },
  { role: "Scenario",        name: "Jun Misaki / Shunya Abe" },
  { role: "Localization",    name: "Jun Misaki" },
  { role: "Programming",     name: "Shunya Abe (AI-assisted)" },
  { role: "UI Design",       name: "Shunya Abe (AI-assisted)" },
  { role: "Illustration",    name: "Shunya Abe (AI-assisted)" },
  { role: "Background Art",  name: "Shunya Abe (AI-assisted)" },
  { role: "2D Animation",    name: "Shunya Abe (AI-assisted)" },
  { role: "Music",           name: "Shunya Abe (AI-assisted)" },
  { role: "Sound Effects",   name: "Shunya Abe (AI-assisted)" },
  { role: "Special Thanks",  name: "Playtesters & Everyone Who Played" },
  { heading: "AI & Creative Tools" },
  { name: "ChatGPT (GPT-5.6 Sol)" },
  { name: "GPT-6 Astra" },
  { name: "GPT-Image-2.5" },
  { name: "OpenMusic AI" },
  { name: "Codex" },
  { name: "Claude" },
  { name: "Blender" },
  { name: "Orca" },
];

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx   audio.js の createSfx()
 * @param {Function}  opts.onMemory  (memory) => Promise<void>
 *        回想を1枚映すたびに呼ぶ。呼び出し側が showScene を通す
 * @param {Function}  opts.onBoard   () => Promise<void>
 *        TOP PLAYERS に移るときに1度だけ呼ぶ。ここから先は同じ画面
 * @param {Function}  opts.onBackToTitle () => void
 *        The End の「タイトルへ」が押されたら呼ぶ
 */
export function initEndingScene({ lang, sfx, onMemory, onBoard, onBackToTitle }) {
  /* ---- 回想 ---------------------------------------------------- */
  const memoryScene = document.getElementById("scene-memory");
  const backdrop = /** @type {HTMLImageElement} */ (document.getElementById("memoryBackdrop"));
  const cardHost = document.getElementById("memoryCard");
  const memoryCast = {
    martin: {
      character: "Martin", clip: "martin_talk03",
      canvas: document.getElementById("memoryMartin"),
      bubble: document.getElementById("memoryBubbleMartin"),
      text: document.getElementById("memoryTextMartin"),
      anim: null,
    },
    catherine: {
      character: "Catherine", clip: "catherine_talk01",
      canvas: document.getElementById("memoryCatherine"),
      bubble: document.getElementById("memoryBubbleCatherine"),
      text: document.getElementById("memoryTextCatherine"),
      anim: null,
    },
  };

  const card = buildPromptCard({ interactive: false });
  cardHost.append(card.slot);

  /* ---- TOP PLAYERS / スタッフロール / The End ------------------- */
  const endScene = document.getElementById("scene-ending");
  const boardEl = document.getElementById("topPlayers");
  const boardHeading = document.getElementById("topPlayersHeading");
  const boardList = document.getElementById("topPlayersList");
  const creditsEl = document.getElementById("credits");
  const creditsRoll = document.getElementById("creditsRoll");
  const endLabel = document.getElementById("endLabel");
  const titleBtn = /** @type {HTMLButtonElement} */ (document.getElementById("backToTitleBtn"));

  /** @type {ReturnType<typeof createSpriteAnim>[]} */
  const walkers = [];

  let uiLang = lang;
  let visible = false;

  /** いま待っているものを解く。押されたら先へ送るために持っておく */
  let release = null;

  /** 立ち絵は一度読めば使い回す */
  const castReady = Promise.all(
    Object.values(memoryCast).map(async (c) => {
      try {
        const clip = await loadClip(c.character, c.clip);
        c.anim = createSpriteAnim(c.canvas, clip);
        c.anim.pose();                 // 口は閉じたまま。回想なので喋らせない
        c.canvas.hidden = false;
      } catch (err) {
        console.error("[ending] failed to load", c.clip, err);
        c.canvas.hidden = true;
      }
    })
  );

  const walkersReady = Promise.all(
    [
      { id: "endMartinWalk",    character: "Martin",    clip: "martin_walk" },
      { id: "endCatherineWalk", character: "Catherine", clip: "catherine_walk" },
    ].map(async ({ id, character, clip }) => {
      const canvas = /** @type {HTMLCanvasElement} */ (document.getElementById(id));
      try {
        const data = await loadClip(character, clip);
        const anim = createSpriteAnim(canvas, data);
        walkers.push(anim);
        if (visible) playWalker(anim);
      } catch (err) {
        console.error("[ending] failed to load", clip, err);
        canvas.hidden = true;
      }
    })
  );

  function playWalker(anim) {
    if (reduceMotion?.matches) anim.pose();
    else anim.start();
  }

  /**
   * 決まった時間だけ待つ。**待っているあいだに押されたら即座に返る。**
   * 回想を飛ばしたい人を待たせないため。
   */
  function hold(ms) {
    return new Promise((resolve) => {
      const done = () => {
        clearTimeout(timer);
        release = null;
        resolve();
      };
      const timer = setTimeout(done, ms);
      release = done;
    });
  }

  /** 画面のどこを押しても、いま待っているものを終わらせる */
  function skip() {
    if (!visible) return;
    release?.();
  }

  function onKeyDown(e) {
    if (!visible || e.isComposing) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      skip();
    }
  }

  memoryScene.addEventListener("click", skip);
  endScene.addEventListener("click", skip);
  window.addEventListener("keydown", onKeyDown);

  // この画面はどこを押しても先へ送るので、ボタンの押下は伝播を止める
  titleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    sfx?.play("confirm");
    onBackToTitle?.();
  });

  /**
   * 回想を1枚組む。その日の会話の**最後のやりとり**を残すので、
   * 参照画像と同じく二人ぶんの吹き出しが並ぶ。
   */
  function fillMemory(memory) {
    backdrop.hidden = !memory.image;
    if (memory.image) backdrop.src = memory.image;

    fillPromptCard(card, memory.winner ?? { author: "", text: "", likes: 0 });
    // 2枚目からは同じ画面のまま中身だけ入れ替わるので、札の出現を掛け直す
    cardHost.style.animation = "none";
    void cardHost.offsetWidth;
    cardHost.style.animation = "";

    for (const [who, c] of Object.entries(memoryCast)) {
      const last = [...(memory.lines ?? [])].reverse().find((l) => l.who === who);
      c.text.textContent = last?.text ?? "";
      c.bubble.hidden = !last;
    }
  }

  function fillBoard(players) {
    const s = t(uiLang);
    boardHeading.textContent = s.topPlayers;
    boardList.replaceChildren();

    for (const player of players) {
      const row = document.createElement("li");
      row.className = "pixel-frame top-player";

      const name = document.createElement("span");
      name.className = "top-player__name";
      name.textContent = player.name;

      const badge = document.createElement("span");
      badge.className = "like-btn top-player__badge";
      badge.setAttribute("aria-hidden", "true");

      const likes = document.createElement("span");
      likes.className = "top-player__likes";
      likes.textContent = String(player.likes);

      row.append(name, badge, likes);
      boardList.append(row);
    }
  }

  function fillCredits() {
    creditsRoll.replaceChildren();
    for (const item of CREDITS) {
      const line = document.createElement("p");
      if (item.heading) {
        line.className = "credits__heading";
        line.textContent = item.heading;
      } else {
        line.className = "credits__line";
        line.textContent = item.role ? `${item.role}: ${item.name}` : item.name;
      }
      creditsRoll.append(line);
    }
  }

  /** 真ん中の入れ替え。ロゴと歩く二人はそのまま */
  function showPanel(which) {
    boardEl.hidden = which !== "board";
    creditsEl.hidden = which !== "credits";
    endLabel.hidden = which !== "end";
    // タイトルへ戻れるのは締めたあとだけ
    titleBtn.hidden = which !== "end";
    if (which === "end") titleBtn.textContent = t(uiLang).backToTitle;
  }

  return {
    setLang(l) {
      uiLang = l;
    },

    /** 素材を先に読んでおく。ラストシーンのあいだに呼んでおくと待ちが消える */
    prepare() {
      return Promise.all([castReady, walkersReady]);
    },

    /**
     * 締めを最後まで流す。呼び出し側は await するだけでよい。
     * @param {{memories: object[], topPlayers: object[]}} ending
     */
    async play(ending) {
      visible = true;

      for (const memory of ending?.memories ?? []) {
        fillMemory(memory);
        await onMemory?.(memory);
        await hold(MEMORY_MS);
      }

      await onBoard?.();

      fillBoard(ending?.topPlayers ?? []);
      showPanel("board");
      walkers.forEach(playWalker);
      await hold(MEMORY_MS);

      fillCredits();
      showPanel("credits");
      // 流れ切るまで。途中で押されたら飛ばせる
      creditsRoll.style.animation = "none";
      void creditsRoll.offsetWidth;            // 巻き戻してから掛け直す
      creditsRoll.style.animation = "";
      await hold(reduceMotion?.matches ? 4000 : CREDITS_MS);

      showPanel("end");
      endLabel.textContent = t(uiLang).theEnd;
      await hold(END_SETTLE_MS);
    },

    /** 画面を離れるときに呼ぶ。裏で rAF を回し続けない */
    stop() {
      visible = false;
      release = null;
      walkers.forEach((a) => a.stop());
      Object.values(memoryCast).forEach((c) => c.anim?.stop());
    },
  };
}
