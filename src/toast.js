/**
 * 通知（「○○が参加しました」など）
 *
 * シーンの外、ステージ直下に置いてある。どの画面に居ても同じ場所に出したいので、
 * .scene の中ではなく .stage の子にしてある（会話中でも Prompt 画面でも届く）。
 *
 * 出す位置は左下。上はカード、下の中央はヒント、右下は BGM のトグルが居るので、
 * そのどれとも重ならない場所を選んである。
 */

/** 1枚を出しておく時間 ms */
const LIFE_MS = 3600;

/** 同時に出しておく上限。多すぎると画面が埋まる */
const MAX_SHOWN = 4;

export function createToaster() {
  const root = document.getElementById("toasts");

  /**
   * 1枚出す。消えるまで待つ必要はない。
   * @param {string} text
   */
  function show(text) {
    const el = document.createElement("li");
    el.className = "toast";
    el.textContent = text;
    root.append(el);

    while (root.children.length > MAX_SHOWN) root.firstElementChild.remove();

    // 進行の判断には使わないので、タブが裏に回って
    // アニメーションが止まっても困らない（scenes.js 冒頭のメモと同じ話）
    setTimeout(() => {
      el.classList.add("is-leaving");
      setTimeout(() => el.remove(), 320);
    }, LIFE_MS);
  }

  return {
    show,

    /** 画面を離れるときなどに、出ているものを消す */
    clear() {
      root.replaceChildren();
    },
  };
}
