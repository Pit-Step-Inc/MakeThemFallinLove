/**
 * 親密度ゲージ
 *
 * 素材は assets/UI/affection.png。**枠の内側は抜けている**ので、
 * 下に敷いた帯を伸び縮みさせると、そこだけ溜まって見える。
 *
 * 通知やコードの札と同じく .scene の外・.stage 直下に置いてある。
 * Prompt 入力と、生成された次の展開の両方で同じ場所に出したいため。
 *
 * 値は 0〜100。回ごとの増減をサーバーが足し込んだものが降ってくる
 * （tools/rooms.py の affinity）ので、ここは映すだけ。
 */

export const AFFINITY_MAX = 100;

export function createAffection() {
  const root = document.getElementById("affection");
  const fill = document.getElementById("affectionFill");

  let value = 0;

  return {
    get value() {
      return value;
    },

    /** @param {number} next 0〜100 */
    setValue(next) {
      const clamped = Math.max(0, Math.min(AFFINITY_MAX, Number(next) || 0));
      if (clamped === value) return;
      value = clamped;
      // 帯は transform で伸ばす。幅を動かすとレイアウトが毎回走る
      fill.style.setProperty("--affection", String(value / AFFINITY_MAX));
      root.setAttribute("aria-valuenow", String(value));
    },

    show() {
      root.hidden = false;
    },

    hide() {
      root.hidden = true;
    },
  };
}
