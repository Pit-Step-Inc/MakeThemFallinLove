/**
 * 部屋の選択（ホストになる / コードで参加）
 *
 * 名前を決めた直後の画面。
 *   - 「ホストになる」を押すと部屋が建ち、4文字のコードが出る
 *   - ほかの人はそのコードを打って入る
 *
 * 建った／入れたら、画面の隅にコードの札が出たまま先へ進む（main.js の codeChip）。
 */

import { t } from "./i18n.js";

export function initRoomScene({ lang, sfx, room, onDone }) {
  const scene    = document.getElementById("scene-room");
  const heading  = document.getElementById("roomHeading");
  const hostBtn  = /** @type {HTMLButtonElement} */ (document.getElementById("hostBtn"));
  const orEl     = document.getElementById("roomOr");
  const codeIn   = /** @type {HTMLInputElement} */ (document.getElementById("roomCodeInput"));
  const joinBtn  = /** @type {HTMLButtonElement} */ (document.getElementById("joinBtn"));
  const hintEl   = document.getElementById("roomHint");

  let uiLang = lang;
  let busy = false;

  function applyStrings() {
    const s = t(uiLang);
    heading.textContent = s.roomHeading;
    hostBtn.textContent = s.beHost;
    orEl.textContent = s.roomOr;
    codeIn.placeholder = s.codePlaceholder;
    joinBtn.textContent = s.joinRoom;
    hintEl.textContent = s.roomHint;
  }

  function syncJoin() {
    joinBtn.disabled = busy || codeIn.value.trim().length === 0;
    hostBtn.disabled = busy;
  }

  /** 入力は大文字だけ。小文字で打たれても直して見せる */
  codeIn.addEventListener("input", () => {
    const pos = codeIn.selectionStart;
    const fixed = codeIn.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (fixed !== codeIn.value) {
      codeIn.value = fixed;
      if (pos !== null) codeIn.setSelectionRange(pos, pos);
    }
    hintEl.textContent = t(uiLang).roomHint;
    syncJoin();
  });

  codeIn.addEventListener("keydown", (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") {
      e.preventDefault();
      join();
    }
  });

  async function host() {
    if (busy) return;
    busy = true;
    syncJoin();
    sfx?.play("confirm");

    await room.host(currentName());
    onDone();
  }

  async function join() {
    if (busy || !codeIn.value.trim()) return;
    busy = true;
    syncJoin();
    sfx?.play("confirm");

    try {
      await room.join(codeIn.value, currentName());
    } catch (err) {
      // コード違いはここで引き返す。黙って一人用に落とさない
      sfx?.play("cancel");
      hintEl.textContent = err?.status === 404
        ? t(uiLang).roomNotFound
        : t(uiLang).roomJoinFailed;
      busy = false;
      syncJoin();
      codeIn.select();
      return;
    }
    onDone();
  }

  let nameOf = () => "";
  const currentName = () => nameOf();

  hostBtn.addEventListener("click", host);
  joinBtn.addEventListener("click", join);

  applyStrings();
  syncJoin();

  return {
    /** タイトルで言語が変わったら呼ぶ */
    setLang(l) {
      uiLang = l;
      applyStrings();
    },

    /** ニックネームの取り出し方を渡す。入った名前で部屋に参加する */
    useName(fn) {
      nameOf = fn;
    },

    /** シーンが表示されたあとに呼ぶ */
    focus() {
      busy = false;
      applyStrings();
      syncJoin();
      hostBtn.focus();
    },
  };
}
