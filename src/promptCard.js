/**
 * Prompt カード（投稿1件ぶんの札）
 *
 * 参照: assets/reference_image/InputPrompt.png, scene_change.png
 *
 * 入力フェーズ（promptScene）と切り替え画面（sceneChange）の両方で使うので、
 * DOM の組み立てだけをここに置いて、いいねを押せるかどうかや並べ替えは
 * 呼び出し側に任せている。
 */

/**
 * @param {object}  opts
 * @param {boolean} opts.interactive いいねを押せるか。押せない画面では span で出す
 * @returns {{slot: HTMLLIElement, name: HTMLElement, body: HTMLElement,
 *            likes: HTMLElement, like: HTMLElement}}
 */
export function buildPromptCard({ interactive = true } = {}) {
  const slot = document.createElement("li");
  slot.className = "prompt-card-slot";

  const card = document.createElement("div");
  card.className = "pixel-panel prompt-card";

  const name = document.createElement("span");
  name.className = "prompt-card__name";
  const body = document.createElement("p");
  body.className = "prompt-card__text";
  const likes = document.createElement("span");
  likes.className = "prompt-card__likes";
  card.append(name, body, likes);

  // 押せない画面では button にしない。見た目は同じでフォーカスが当たらない
  const like = document.createElement(interactive ? "button" : "span");
  like.className = "like-btn";
  if (interactive) /** @type {HTMLButtonElement} */ (like).type = "button";
  else like.setAttribute("aria-hidden", "true");

  slot.append(card, like);
  return { slot, name, body, likes, like };
}

/**
 * 中身を入れる。
 * @param {ReturnType<typeof buildPromptCard>} els
 * @param {{author: string, text: string, likes: number}} data
 */
export function fillPromptCard(els, { author, text, likes }) {
  els.name.textContent = author;
  els.body.textContent = text;
  els.likes.textContent = String(likes);
}
