/**
 * エンディング
 *
 * 参照: assets/reference_image/Memory_001.png, Memory_002.png（回想）
 *       assets/reference_image/Ending_001.png（TOP PLAYERS）
 *       assets/reference_image/Ending_002.png（The End）
 *
 * Catherine の独り言が終わったら、ここで締める。
 *
 * **締めが流れるのは親密度が満タンのときだけ。** 届かなかったときは
 * 「まだ終わっていない」の面だけ出して、タイトルへ戻ってもらう（showUnfinished）。
 *
 * 満タンで迎えたときの順番は
 *
 *   1. 未来   … 10年後・20年後・30年後。3日間の出来事に連なる情景の上で、
 *                二人が歳を重ねて幸せになるまで（assets/Prompt/005.txt）
 *   2. TOP PLAYERS … もらったいいねの合計が多かった3人
 *   3. スタッフロール
 *   4. The End
 *
 * **2〜4 は同じ画面**で、ロゴと歩く二人は出しっぱなしのまま真ん中だけ
 * 入れ替える（参照画像の2枚が同じ構図なので、切り替えると絵が跳ねる）。
 *
 * BGM は 1 に入るところで EndRoll に差し替えて、最後まで流しっぱなし。
 *
 * **未来の3場面は自動では進まない。**「つぎへ」を押すまでその年のまま待つ
 * （読む速さは人それぞれなので、時間で送ると読み終わらないうちに次へ行く）。
 * TOP PLAYERS から先は放っておいても流れ、スタッフロールは CSS の
 * アニメーションが終わったところで The End に移る。
 */

import { t } from "./i18n.js";
import { loadClip, createSpriteAnim } from "./spriteAnim.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/**
 * TOP PLAYERS を映しておく時間 ms。**飛ばせないので、この時間ぶん必ず出る。**
 * **未来の3場面はここでは使わない**（時間ではなく「つぎへ」で送る）
 */
const MEMORY_MS = 6000;

/** 未来の場面の年（tools/story.py の FUTURE_YEARS と揃える） */
const FUTURE_YEARS = [10, 20, 30];

/**
 * 未来の立ち絵のありか。**年ごとに描き下ろした1枚絵**で、
 * ふだんのコマ送りのスプライトとは別物（assets/<名前>/future/）。
 * 知らない年が来たら最初の年の絵にしておく（絵が消えるよりはよい）。
 *
 * @param {"Martin"|"Catherine"} character
 * @param {number} year
 */
function futurePortrait(character, year) {
  const n = FUTURE_YEARS.includes(year) ? year : FUTURE_YEARS[0];
  return `assets/${character}/future/${n}_years_later_${character.toLowerCase()}.png`;
}

/** スタッフロールが流れ切るまで ms（style.css の credits-roll と揃える） */
const CREDITS_MS = 16000;

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
  const yearEl = document.getElementById("memoryYear");
  const nextBtn = /** @type {HTMLButtonElement} */ (document.getElementById("memoryNext"));
  const memoryCast = {
    martin: {
      character: "Martin",
      portrait: /** @type {HTMLImageElement} */ (document.getElementById("memoryMartin")),
      bubble: document.getElementById("memoryBubbleMartin"),
      text: document.getElementById("memoryTextMartin"),
    },
    catherine: {
      character: "Catherine",
      portrait: /** @type {HTMLImageElement} */ (document.getElementById("memoryCatherine")),
      bubble: document.getElementById("memoryBubbleCatherine"),
      text: document.getElementById("memoryTextCatherine"),
    },
  };

  /* ---- TOP PLAYERS / スタッフロール / The End ------------------- */
  const endScene = document.getElementById("scene-ending");
  const boardEl = document.getElementById("topPlayers");
  const boardHeading = document.getElementById("topPlayersHeading");
  const boardList = document.getElementById("topPlayersList");
  const creditsEl = document.getElementById("credits");
  const creditsRoll = document.getElementById("creditsRoll");
  const endLabel = document.getElementById("endLabel");
  const notOverEl = document.getElementById("notOver");
  const notOverTitle = document.getElementById("notOverTitle");
  const notOverBody = document.getElementById("notOverBody");
  const titleBtn = /** @type {HTMLButtonElement} */ (document.getElementById("backToTitleBtn"));

  /** @type {ReturnType<typeof createSpriteAnim>[]} */
  const walkers = [];

  let uiLang = lang;
  let visible = false;

  /** いま待っているものを解く。押されたら先へ送るために持っておく */
  let release = null;

  /**
   * いま待っているものを「つぎへ」でしか進められないか。
   * **未来の3場面がこれ。** 画面のどこを押しても進むと、読んでいる途中で
   * 誰かが触っただけで次の年へ飛んでしまう
   */
  let buttonOnly = false;

  /**
   * 未来の立ち絵を先読みしておく。
   *
   * 場面が変わるたびに読みに行くと、1枚 1.3MB あるので切り替わりで
   * 立ち絵が消える。prepare() はラストシーンの独り言のあいだに呼ばれるので、
   * そこで6枚とも読み終えておく。読めなかった絵があっても締めは止めない。
   */
  const castReady = Promise.all(
    FUTURE_YEARS.flatMap((year) =>
      Object.values(memoryCast).map((c) => new Promise((resolve) => {
        const img = new Image();
        img.onload = img.onerror = () => resolve();
        img.src = futurePortrait(c.character, year);
      }))
    )
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
   * 待たされたくない人のため。
   *
   * @param {{skippable?: boolean}} [opts]
   *        skippable: false にすると押しても飛ばせない。
   *        **スタッフロールがこれ。** 名前が出ている場所なので、
   *        画面のどこかに触れただけで流し飛ばされないようにしてある
   */
  function hold(ms, { skippable = true } = {}) {
    return new Promise((resolve) => {
      const done = () => {
        clearTimeout(timer);
        release = null;
        resolve();
      };
      const timer = setTimeout(done, ms);
      // 飛ばせない待ちのあいだは、前の待ちの解除役を残さない
      release = skippable ? done : null;
    });
  }

  /**
   * **押されるまで待つ。** 未来の3場面はここで止まる。
   *
   * 時間で送ると、読み終わらないうちに次の年へ行ってしまう。
   * ボタンのほかに、画面のどこを押しても・Enter でも進める（skip と同じ口）。
   */
  function waitForNext() {
    nextBtn.textContent = t(uiLang).next;
    nextBtn.hidden = false;
    buttonOnly = true;
    // キーだけで遊んでいる人がそのまま Enter で送れるように焦点を当てる。
    // マウスで進む人には輪郭は出ない（:focus-visible なので）
    nextBtn.focus();
    return new Promise((resolve) => {
      release = () => {
        release = null;
        buttonOnly = false;
        nextBtn.hidden = true;
        resolve();
      };
    });
  }

  /**
   * 画面のどこを押しても、いま待っているものを終わらせる。
   * **「つぎへ」待ちのあいだは効かない**（そのときはボタンだけが進める）
   */
  function skip() {
    if (!visible || buttonOnly) return;
    release?.();
  }

  function onKeyDown(e) {
    if (!visible || e.isComposing) return;
    // 「つぎへ」に焦点があるときは横取りしない。
    // preventDefault するとボタン本来の Enter / Space が効かなくなる
    if (e.target === nextBtn) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      skip();
    }
  }

  memoryScene.addEventListener("click", skip);
  // 画面全体のクリックと二重に拾わないよう、ここで止めてから送る。
  // skip() は「つぎへ」待ちでは効かないので、直に解く
  nextBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (!visible) return;
    release?.();
  });
  endScene.addEventListener("click", skip);
  window.addEventListener("keydown", onKeyDown);

  // この画面はどこを押しても先へ送るので、ボタンの押下は伝播を止める
  titleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    sfx?.play("confirm");
    onBackToTitle?.();
  });

  /**
   * 未来の場面を1枚組む。二人の台詞を1往復ぶん並べる。
   */
  function fillScene(scene) {
    backdrop.hidden = !scene.image;
    if (scene.image) backdrop.src = scene.image;

    yearEl.textContent = t(uiLang).yearsLater(scene.year);
    // 2枚目からは同じ画面のまま中身だけ入れ替わるので、見出しの出現を掛け直す
    yearEl.style.animation = "none";
    void yearEl.offsetWidth;
    yearEl.style.animation = "";

    for (const [who, c] of Object.entries(memoryCast)) {
      // 立ち絵はこの場面の年のもの。10年後・20年後・30年後で描き分けてある
      c.portrait.src = futurePortrait(c.character, scene.year);

      const line = (scene.lines ?? []).find((l) => l.who === who);
      c.text.textContent = line?.text ?? "";
      c.bubble.hidden = !line;
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
    notOverEl.hidden = which !== "unfinished";
    // タイトルへ戻れるのは、締めたあとか、続きがあると告げたとき
    titleBtn.hidden = which !== "end" && which !== "unfinished";
    if (!titleBtn.hidden) titleBtn.textContent = t(uiLang).backToTitle;
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
     * **親密度が満タンに届かなかったとき。**
     * 締めは流さず、続きがあることだけ告げてタイトルへ戻ってもらう。
     */
    async showUnfinished() {
      visible = true;
      notOverTitle.textContent = t(uiLang).notOverTitle;
      notOverBody.textContent = t(uiLang).notOverBody;
      await onBoard?.();               // 締めと同じロゴ＋歩く二人の画面
      nextBtn.hidden = true;
      showPanel("unfinished");
      walkers.forEach(playWalker);
    },

    /**
     * 締めを最後まで流す。呼び出し側は await するだけでよい。
     * @param {{scenes: object[], topPlayers: object[]}} ending
     */
    async play(ending) {
      visible = true;

      // **未来の3場面は時間で送らない。** 読み終えた人が「つぎへ」を
      // 押すまでその年のまま待つ（TOP PLAYERS から先は今までどおり流れる）
      for (const scene of ending?.scenes ?? []) {
        fillScene(scene);
        await onMemory?.(scene);
        await waitForNext();
      }

      await onBoard?.();

      fillBoard(ending?.topPlayers ?? []);
      showPanel("board");
      walkers.forEach(playWalker);
      // スタッフロールと同じく飛ばせない。上位3人の名前が出ている場所なので、
      // 誰かが画面に触れただけで消えてしまわないようにする
      await hold(MEMORY_MS, { skippable: false });

      fillCredits();
      showPanel("credits");
      // **流れ切るまで飛ばせない。** 名前が出ている場所なので、
      // 誰かが画面に触れただけで飛んでしまわないようにする
      creditsRoll.style.animation = "none";
      void creditsRoll.offsetWidth;            // 巻き戻してから掛け直す
      creditsRoll.style.animation = "";
      await hold(reduceMotion?.matches ? 4000 : CREDITS_MS, { skippable: false });

      showPanel("end");
      endLabel.textContent = t(uiLang).theEnd;
      await hold(END_SETTLE_MS);
    },

    /** 画面を離れるときに呼ぶ。裏で rAF を回し続けない */
    stop() {
      visible = false;
      release = null;
      buttonOnly = false;
      nextBtn.hidden = true;
      walkers.forEach((a) => a.stop());
      // 未来の立ち絵は1枚絵なので、止めるものは無い
    },
  };
}
