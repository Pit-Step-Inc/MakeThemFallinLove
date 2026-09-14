/**
 * ルーム（Prompt の共有）
 *
 * **ホストが部屋を建て、ほかの人はコードで入る。**
 * サーバー側は tools/rooms.py。
 *
 * 【サーバーが無くても遊べるようにしてある】
 * 静的ホスティング（GitHub Pages など）に置くと /api/ は 404 になる。
 * そのときは同じ形のローカル実装に落ちて、今までどおり一人で遊べる。
 * 呼び出し側は online を見ずに同じメソッドを呼べばよい。
 *
 * 【カウントダウンは全員が揃ってから】
 * 会話を読み終えて Prompt 画面に着いた人が ready() を打つ。部屋の全員が
 * ready になった瞬間に制限時間が始まる（長さの判断はサーバー側）。
 * 揃わないときは**ホストだけ** forceStart() で先に始められる。
 *
 * 【参加した時点から鼓動を打つ】
 * 会話を読んでいるあいだも定期的に様子を見に行く。これで
 *   - 「○○が参加しました」がどの画面に居ても届く
 *   - 生きていることがサーバーに伝わり、待ち合わせから外されない
 * の2つが同時に片付く。
 *
 * 【時刻はサーバーの「残り ms」で合わせる】
 * 締め切りの絶対時刻をそのまま配ると、端末の時計がずれているぶんだけ
 * 残り秒数が食い違う。残り時間だけを配って、受け取った側が
 * performance.now() を基準に置き直せば時計合わせが要らない。
 */

const API = "api";

/** Prompt 画面に着くまでの、様子見の間隔 ms */
const HEARTBEAT_MS = 2500;

/** 部屋ごとに id を覚えておく。再読み込みしても同じ人として扱う */
const idKey = (code) => `mtfil.player.${code}`;

function loadPlayerId(code) {
  try {
    return localStorage.getItem(idKey(code)) ?? "";
  } catch {
    return "";
  }
}

function savePlayerId(code, id) {
  try {
    localStorage.setItem(idKey(code), id);
  } catch {
    /* 保存できなくてもその場は遊べる */
  }
}

async function post(path, body) {
  const res = await fetch(`${API}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw Object.assign(new Error(data.error ?? res.statusText), { status: res.status, data });
  }
  return data;
}

/* ---------------------------------------------------------------
   サーバーが居ないときの代役。
   1人ぶんの状態をメモリに持つだけで、返す形はサーバーと同じ。
   --------------------------------------------------------------- */
function createLocalRoom(roundSeconds) {
  let name = "";
  let deadline = null;
  let seq = 0;
  let prompts = [];

  const remaining = () =>
    deadline === null ? null : Math.max(0, Math.round(deadline - performance.now()));

  const state = () => ({
    code: "----",
    isHost: true,
    hostName: name,
    players: 1,
    ready: deadline === null ? 0 : 1,
    names: [name],
    prompts: [...prompts].sort((a, b) => b.likes - a.likes)
      .map((p) => ({ id: p.id, author: p.author, text: p.text, likes: p.likes })),
    remainingMs: remaining(),
    started: deadline !== null,
    roundOver: remaining() === 0,
    myPromptId: prompts[0]?.id ?? null,
    affinity: 0,
    eventSeq: 0,
    events: [],
  });

  const start = () => {
    if (deadline === null) deadline = performance.now() + roundSeconds * 1000;
    return state();
  };

  return {
    enter(playerName) {
      name = playerName;
      return state();
    },
    // 一人しか居ないので、着いた時点で全員そろっている
    ready: start,
    forceStart: start,
    submit(text) {
      if (remaining() === 0 || prompts.length) return state();
      seq += 1;
      prompts.push({ id: `l${seq}`, author: name, text, likes: 0 });
      return state();
    },
    like(promptId) {
      const p = prompts.find((x) => x.id === promptId);
      if (p) p.likes += 1;
      return state();
    },
    state,
    reset() {
      deadline = null;
      prompts = [];
      seq = 0;
    },
  };
}

/**
 * @param {object} opts
 * @param {number} opts.roundSeconds サーバーが居ないときに使う制限時間
 */
export function createRoom({ roundSeconds = 30 } = {}) {
  let code = "";
  /** 生成される会話をどちらで書かせるか。部屋を建てた人の言語に揃える */
  let lang = "en";
  let playerId = "";
  let isHost = false;
  let online = false;
  let local = null;

  /** サーバーに要求するときの起点。ここより新しい通知だけ返ってくる */
  let sinceEvent = 0;

  /** 実際に出し終えた通知の番号。鼓動とポーリングが同時に走ると
      同じ sinceEvent で2本飛んで同じ通知が返ってくるので、ここで止める */
  let dispatched = 0;
  let heartbeat = 0;

  /** @type {((event: {type: string, name: string}) => void)[]} */
  const listeners = [];

  /** @type {((state: object) => void)[]} */
  const watchers = [];

  /** サーバーに繋がらなくなったら、そこから先はローカルで続ける */
  function fallback() {
    if (!online) return;
    console.warn("[room] server unreachable — continuing offline");
    online = false;
    clearInterval(heartbeat);
    heartbeat = 0;
  }

  /**
   * サーバーの返事を通す。通知はここ一箇所で拾うので、
   * 鼓動とポーリングが同時に走っても取りこぼしも二重も起きない。
   */
  function take(state) {
    if (!state) return state;


    for (const event of state.events ?? []) {
      if (event.seq <= dispatched) continue;   // もう出した
      dispatched = event.seq;
      for (const fn of listeners) {
        try {
          fn(event);
        } catch (err) {
          console.error("[room] listener failed", err);
        }
      }
    }

    if (typeof state.eventSeq === "number") sinceEvent = Math.max(sinceEvent, state.eventSeq);
    if (typeof state.isHost === "boolean") isHost = state.isHost;

    // 鼓動でもポーリングでも、部屋の様子が届いたら知らせる。
    // 親密度のように「どの画面でも同じ値を映したいもの」はここで拾う
    for (const fn of watchers) {
      try {
        fn(state);
      } catch (err) {
        console.error("[room] watcher failed", err);
      }
    }
    return state;
  }

  async function pulse() {
    if (!online) return;
    try {
      const res = await fetch(
        `${API}/state?code=${encodeURIComponent(code)}&playerId=${encodeURIComponent(playerId)}&sinceEvent=${sinceEvent}`
      );
      if (!res.ok) throw new Error(res.statusText);
      take(await res.json());
    } catch {
      fallback();
    }
  }

  /** 入れた／建てられた あとの共通処理 */
  function settle(data) {
    code = data.code;
    playerId = data.playerId;
    isHost = Boolean(data.isHost);
    savePlayerId(code, playerId);
    online = true;
    // 入った時点までの通知は流さない（自分の参加も含めて）
    sinceEvent = data.eventSeq ?? 0;
    dispatched = sinceEvent;

    // 会話を読んでいるあいだも様子を見に行く。
    // 通知が届くのと、待ち合わせから外されないのが同時に片付く
    clearInterval(heartbeat);
    heartbeat = setInterval(pulse, HEARTBEAT_MS);
    return data;
  }

  // **タブが裏に回ると setInterval は最大1分まで間引かれる。**
  // 戻ってきた瞬間に一度打ち直して、溜まった通知と残り時間を取り戻す
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") pulse();
  });

  function goLocal(name) {
    console.warn("[room] offline mode");
    online = false;
    isHost = true;
    code = "";
    local = createLocalRoom(roundSeconds);
    return local.enter(name);
  }

  return {
    get online() {
      return online;
    },
    get code() {
      return code;
    },
    get isHost() {
      return isHost;
    },
    get playerId() {
      return playerId;
    },

    /** 「○○が参加しました」などを受け取る */
    onEvent(fn) {
      listeners.push(fn);
    },

    /** 部屋の様子が届くたびに受け取る（親密度など） */
    onState(fn) {
      watchers.push(fn);
    },

    /**
     * 部屋を建てる。建てた人がホストになる。
     * サーバーに繋がらなければ一人用に落ちる（例外は投げない）。
     */
    /** タイトルで言語が決まったら呼ぶ。部屋を建てる/入るときに一緒に送る */
    setLang(l) {
      lang = l;
    },

    async host(name) {
      try {
        return settle(await post("host", { name, lang }));
      } catch (err) {
        console.warn("[room] cannot host:", err?.message ?? err);
        return goLocal(name);
      }
    },

    /**
     * コードで入る。
     * **コードが違うときは例外を投げる**（入力し直してもらうため、
     * ここだけは黙って一人用に落とさない）。
     */
    async join(inputCode, name) {
      const wanted = String(inputCode ?? "").trim().toUpperCase();
      const data = await post("join", { code: wanted, name, lang, playerId: loadPlayerId(wanted) });
      return settle(data);
    },

    /**
     * Prompt 画面に着いた合図。
     * **部屋の全員が揃った瞬間**にカウントダウンが始まる（判断はサーバー側）。
     */
    async ready() {
      if (!online) return take(local.ready());
      try {
        return take(await post("ready", { code, playerId, sinceEvent }));
      } catch {
        fallback();
        return take(local?.ready());
      }
    },

    /** 揃うのを待たずに始める。ホストだけ効く */
    async forceStart() {
      if (!online) return take(local.forceStart());
      try {
        return take(await post("force-start", { code, playerId, sinceEvent }));
      } catch (err) {
        if (err.status === 403 && err.data) return take(err.data);
        fallback();
        return take(local?.forceStart());
      }
    },

    /**
     * いちばんいいねが多かった Prompt から次の展開を作らせる。
     * **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る（判断はサーバー側）。
     * 10秒ほどかかるので、結果は state().story を見て待つ。
     */
    async story() {
      if (!online) return take(local.state());
      try {
        return take(await post("story", { code, playerId, sinceEvent }));
      } catch {
        fallback();
        return take(local?.state());
      }
    },

    /**
     * ランダムイベント（assets/Prompt/004.txt）を作らせる。
     * **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
     * 結果は state().event を見て待つ。
     */
    async event() {
      if (!online) return take(local.state());
      try {
        return take(await post("event", { code, playerId, sinceEvent }));
      } catch {
        fallback();
        return take(local?.state());
      }
    },

    /**
     * 10年後・20年後・30年後（assets/Prompt/005.txt）を作らせる。
     * **親密度が満タンで終えたときだけ使う。** 作るのは部屋につき1回だけ。
     */
    async future() {
      if (!online) return take(local.state());
      try {
        return take(await post("future", { code, playerId, sinceEvent }));
      } catch {
        fallback();
        return take(local?.state());
      }
    },

    /**
     * 最後の独り言（assets/Prompt/003.txt）を作らせる。
     * **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
     */
    async finale() {
      if (!online) return take(local.state());
      try {
        return take(await post("finale", { code, playerId, sinceEvent }));
      } catch (err) {
        if (err.status === 409 && err.data) return take(err.data);
        fallback();
        return take(local?.state());
      }
    },

    /** Prompt を出す。1人1つまでで、2つ目はサーバーが弾く */
    async submit(text) {
      if (!online) return take(local.submit(text));
      try {
        return take(await post("prompt", { code, playerId, text, sinceEvent }));
      } catch (err) {
        // 409 は「もう出している」「時間切れ」。状態はそのまま返ってくる
        if (err.status === 409 && err.data) return take(err.data);
        fallback();
        return take(local?.submit(text));
      }
    },

    async like(promptId) {
      if (!online) return take(local.like(promptId));
      try {
        return take(await post("like", { code, playerId, promptId, sinceEvent }));
      } catch {
        fallback();
        return take(local?.like(promptId));
      }
    },

    /** いまの部屋の様子。Prompt 画面はこれを細かく呼ぶ */
    async state() {
      if (!online) return take(local.state());
      try {
        const res = await fetch(
          `${API}/state?code=${encodeURIComponent(code)}&playerId=${encodeURIComponent(playerId)}&sinceEvent=${sinceEvent}`
        );
        if (!res.ok) throw new Error(res.statusText);
        return take(await res.json());
      } catch {
        fallback();
        return take(local?.state());
      }
    },

    /** ローカルで遊んでいるときだけ意味がある。頭からやり直す */
    reset() {
      local?.reset();
    },
  };
}
