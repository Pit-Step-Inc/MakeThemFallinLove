/**
 * Prompt 入力フェーズ
 *
 * 参照: assets/reference_image/InputPrompt.png
 *
 * 会話が終わると吹き出しと入れ替わりでここに入る。背景も立ち絵もそのままなので
 * **シーンは切り替えない**（showScene は一度黒に落としてから次を出すので、
 * 同じ場所で使うと画面が暗転してしまう）。
 *
 * 画面の中身:
 *   - 上段に投稿カード。いいねの多い順で、押すたびに並べ替わる
 *   - カードの下に いいね ボタン
 *   - 中央に「次の展開は？」＋残り秒数、その下に入力欄
 *
 * 【状態は部屋（room.js）が持つ】
 * 同じ部屋に居る人の Prompt が全員に出る。**Prompt は1人1つまで**で、
 * **カウントダウンは全員が揃ってから**。着いた人から順に ready を打ち、
 * 全員が揃うまでは「みんなを待っています n/m」を出して待つ。
 * 揃わないときは**ホストにだけ**「先に始める」を出す。
 * この画面はサーバーの言うことを映すだけで、手元では何も決めない。
 */

import { t } from "./i18n.js";
import { buildPromptCard, fillPromptCard } from "./promptCard.js";

const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");

/** 上段に並べられる枚数。参照画像の5枠ぶん */
export const MAX_PROMPTS = 5;

/** サーバーが居ないときの制限時間 秒（tools/rooms.py の ROUND_SECONDS と揃える） */
export const TIME_LIMIT = 60;

/**
 * 入力できる長さ。言語ごとに変える（tools/rooms.py の MAX_TEXT と揃える）。
 *
 * 英語は同じ内容を書くのに語と語の空白ぶん字数が要るので、日本語より長く取る。
 * 上段の札（.prompt-card）に収まる範囲であること。
 */
export const MAX_LENGTH = { ja: 40, en: 50 };

/** 部屋の様子を取りに行く間隔 ms */
const POLL_MS = 600;

/** 残り秒数の表示を描き直す間隔 ms */
const TICK_MS = 200;

/** 並べ替えの見せ方。動かす前後の位置差を transform で埋めてから戻す */
const SLIDE_MS = 260;

/**
 * 先頭 limit 「文字」に切り詰める。
 * maxlength 属性は UTF-16 単位で数えるので、絵文字や結合文字が
 * 2 文字分を消費してしまう（nickname.js と同じ理由）。
 */
function clamp(value, limit) {
  const chars = [...value];
  return chars.length > limit ? chars.slice(0, limit).join("") : value;
}

/**
 * @param {object}    opts
 * @param {"en"|"ja"} opts.lang
 * @param {object}    opts.sfx       audio.js の createSfx()
 * @param {object}    opts.room      room.js の createRoom()
 * @param {Function}  opts.onTimeUp  残り 0 秒になったら呼ぶ
 */
export function initPromptScene({ lang, sfx, room, onTimeUp }) {
  const root    = document.getElementById("promptPhase");
  const listEl  = document.getElementById("promptCards");
  const labelEl = document.getElementById("promptLabel");
  const countEl = document.getElementById("promptCount");
  const inputEl = /** @type {HTMLInputElement} */ (document.getElementById("promptInput"));
  const inputLabelEl = document.getElementById("promptInputLabel");
  const startEl = /** @type {HTMLButtonElement} */ (document.getElementById("promptStart"));

  let uiLang = lang;
  let visible = false;
  let finished = false;

  let poller = 0;
  let ticker = 0;
  let deadlineAt = null;        // performance.now() 基準。null はまだ始まっていない
  let latest = { prompts: [], myPromptId: null, roundOver: false, ready: 0, players: 1 };

  /** 出ているカード。Prompt の id → buildPromptCard() の戻り値 */
  const shown = new Map();

  /* ---------------------------------------------------------------
     描画
     --------------------------------------------------------------- */

  /** サーバーが返した順（いいね降順）に、上から MAX_PROMPTS 件だけ出す */
  function applyPrompts(prompts) {
    const list = prompts.slice(0, MAX_PROMPTS);
    const items = [...listEl.children];
    const before = new Map(items.map((el) => [el, el.getBoundingClientRect().left]));

    // 消えた Prompt を片付ける（部屋が新しい回に入ったときくらいしか起きない）
    const ids = new Set(list.map((p) => p.id));
    for (const [id, els] of shown) {
      if (ids.has(id)) continue;
      els.slot.remove();
      shown.delete(id);
    }

    for (const p of list) {
      let els = shown.get(p.id);
      if (!els) {
        els = buildPromptCard();
        els.like.addEventListener("click", () => like(p.id));
        shown.set(p.id, els);
      }
      fillPromptCard(els, p);
      els.like.setAttribute("aria-label", t(uiLang).promptLike);
      // **先頭がいまの一番手。** サーバーがいいね降順で返すので、
      // 左端がそのまま「次の展開に選ばれる Prompt」になる（tools/rooms.py の _ranked）
      els.slot.classList.toggle("is-leading", p === list[0]);
      // append は既にある要素なら「移動」になる。これで並びが順番どおりになる
      listEl.append(els.slot);
    }

    if (reduceMotion?.matches) return;
    for (const el of items) {
      if (!el.isConnected) continue;
      const dx = before.get(el) - el.getBoundingClientRect().left;
      if (!dx) continue;
      el.animate(
        [{ transform: `translateX(${dx}px)` }, { transform: "none" }],
        { duration: SLIDE_MS, easing: "cubic-bezier(.2, .9, .3, 1)" }
      );
    }
  }

  function applyState(state) {
    if (!state) return;
    latest = state;

    applyPrompts(state.prompts ?? []);

    // 残り時間は毎回サーバーの値で置き直す。手元では数えない
    deadlineAt = state.remainingMs == null
      ? null
      : performance.now() + state.remainingMs;

    const s = t(uiLang);
    const waiting = !state.started;

    // 全員が揃うまでは投稿させない。押せないだけだと理由が分からないので、
    // 見出しと案内をそのまま状況の表示に使う
    labelEl.textContent = waiting ? s.waitingForPlayers : s.promptLabel;
    inputEl.disabled = waiting || Boolean(state.myPromptId) || Boolean(state.roundOver);
    inputEl.placeholder = state.roundOver ? s.promptClosed
      : state.myPromptId ? s.promptSent
      : s.promptPlaceholder;

    // 席を立った人が居ると全員が揃わない。ホストだけ先へ進められる
    startEl.hidden = !(waiting && state.isHost);
    startEl.textContent = s.startNow;

    root.classList.toggle("is-waiting", waiting);
    root.classList.toggle("is-sent", Boolean(state.myPromptId));
    root.classList.toggle("is-over", Boolean(state.roundOver));

    tick();
  }

  function secondsLeft() {
    if (deadlineAt === null) return TIME_LIMIT;
    return Math.max(0, Math.ceil((deadlineAt - performance.now()) / 1000));
  }

  /**
   * 残り秒数は「締め切りとの差」から出す。
   * setInterval の回数を数えると、裏に回って間引かれたぶんだけ遅れていく。
   */
  function tick() {
    // まだ始まっていないあいだは、秒数の代わりに揃った人数を出す
    if (deadlineAt === null) {
      countEl.textContent = `${latest.ready ?? 0}/${latest.players ?? 1}`;
      countEl.classList.remove("is-low");
      return;
    }
    const left = secondsLeft();
    countEl.textContent = String(left);
    countEl.classList.toggle("is-low", left <= 5);
    if (left <= 0) timeUp();
  }

  function timeUp() {
    if (finished) return;
    finished = true;
    stopTimers();
    countEl.textContent = "0";
    inputEl.disabled = true;
    root.classList.add("is-over");
    onTimeUp?.();
  }

  /* ---------------------------------------------------------------
     部屋とのやりとり
     --------------------------------------------------------------- */

  async function poll() {
    if (!visible) return;
    applyState(await room.state());
  }

  async function submit() {
    if (finished || inputEl.disabled) return;

    const text = inputEl.value.trim();
    if (!text) return;

    inputEl.disabled = true;              // 二重送信を止める。結果は applyState が決める
    const state = await room.submit(text);
    if (state?.myPromptId) {
      inputEl.value = "";
      sfx?.play("confirm");
    }
    applyState(state);
  }

  startEl.addEventListener("click", async () => {
    startEl.disabled = true;
    sfx?.play("confirm");
    applyState(await room.forceStart());
    startEl.disabled = false;
  });

  async function like(promptId) {
    sfx?.play("confirm");
    applyState(await room.like(promptId));
  }

  function stopTimers() {
    clearInterval(poller);
    clearInterval(ticker);
    poller = 0;
    ticker = 0;
  }

  /* ---------------------------------------------------------------
     入力欄
     --------------------------------------------------------------- */

  inputEl.addEventListener("input", () => {
    const clamped = clamp(inputEl.value, maxLength());
    if (clamped === inputEl.value) return;
    const pos = inputEl.selectionStart;
    inputEl.value = clamped;
    // 切り詰めでカーソルが末尾に飛ばないようにする
    if (pos !== null) {
      const at = Math.min(pos, clamped.length);
      inputEl.setSelectionRange(at, at);
    }
  });

  inputEl.addEventListener("keydown", (e) => {
    // IME 変換中の Enter は確定操作なので拾わない
    if (e.isComposing) return;
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  });

  // 画面のどこを押しても入力欄に戻す。いいね と入力欄自身は除く
  root.addEventListener("click", (e) => {
    if (inputEl.disabled) return;
    if (e.target instanceof Element && e.target.closest("button, input")) return;
    inputEl.focus();
  });

  /** いまの言語で入力できる長さ */
  function maxLength() {
    return MAX_LENGTH[uiLang] ?? MAX_LENGTH.en;
  }

  function applyStrings() {
    const s = t(uiLang);
    labelEl.textContent = s.promptLabel;
    // 文字数は言語で変わるので、属性のほうも言語に追従させる
    inputEl.maxLength = maxLength();
    inputEl.placeholder = s.promptPlaceholder;
    inputLabelEl.textContent = s.promptPlaceholder;
    for (const els of shown.values()) els.like.setAttribute("aria-label", s.promptLike);
  }

  applyStrings();

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
      applyStrings();
    },

    /** 出す前に呼ぶ。カードと残り時間を初期状態に戻す */
    prepare() {
      finished = false;
      deadlineAt = null;
      latest = { prompts: [], myPromptId: null, roundOver: false, ready: 0, players: 1 };
      shown.clear();
      listEl.replaceChildren();
      applyStrings();
      inputEl.value = "";
      inputEl.disabled = false;
      root.classList.remove("is-over", "is-sent", "is-waiting");
      startEl.hidden = true;
      countEl.classList.remove("is-low");
      countEl.textContent = String(TIME_LIMIT);
    },

    /**
     * 表示して「着いた」と伝える。
     * カウントダウンが始まるのは**部屋の全員が揃ってから**で、
     * それまでは待ち合わせの表示のまま（判断は tools/rooms.py 側）。
     */
    async start() {
      root.hidden = false;
      visible = true;
      inputEl.focus();

      ticker = setInterval(tick, TICK_MS);
      poller = setInterval(poll, POLL_MS);

      // 「着いたよ」の合図。全員が揃った瞬間にサーバーが制限時間を切る
      applyState(await room.ready());
    },

    /** 抜けるときに呼ぶ。裏でタイマーとポーリングを回し続けない */
    stop() {
      visible = false;
      stopTimers();
      root.hidden = true;
    },

    /** @returns {{author: string, text: string, likes: number}[]} いいね順の投稿 */
    results() {
      return (latest.prompts ?? []).map((p) => ({
        author: p.author,
        text: p.text,
        likes: p.likes,
      }));
    },
  };
}
