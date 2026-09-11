/**
 * シーン切り替え
 *
 * <section class="scene"> を出し入れするだけの薄いユーティリティ。
 * 画面が増えてもここは変えずに済むように、DOM の構造だけに依存させてある。
 *
 * 【重要】アニメーションの完了を待ってはいけない
 *
 * タブが裏に回る / ウィンドウが他のウィンドウに隠れると、Chrome は
 * document.timeline を止める。実測では performance.now() が 42 秒進んでいても
 * document.timeline.currentTime が 0 のままだった。
 * この状態では CSS transition も Web Animations も進まないので、
 *   await anim.finished
 * は永久に解決せず、シーン遷移がその場で止まってゲームが進まなくなる。
 *
 * そのため進行は setTimeout（裏でも間引かれるだけで必ず発火する）で駆動し、
 * アニメーションはあくまで見た目の飾りとして扱う。
 */

const FADE_MS = 320;

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

let current = null;

function fade(el, from, to, { fill } = {}) {
  // タイムラインが止まっていると再生されないが、それでも進行は止めない
  return el.animate(
    [{ opacity: from }, { opacity: to }],
    { duration: FADE_MS, easing: "ease", fill: fill ?? "none" }
  );
}

/** @param {string} id 表示したい <section class="scene"> の id */
export async function showScene(id) {
  const next = document.getElementById(id);
  if (!next) throw new Error(`scene not found: ${id}`);
  if (next === current) return next;

  const prev = current;
  current = next;

  if (prev) {
    prev.style.pointerEvents = "none";
    // fill:"forwards" が無いと完了フレームで opacity:1 に戻ってちらつく
    const out = fade(prev, 1, 0, { fill: "forwards" });
    await wait(FADE_MS);
    prev.hidden = true;
    out.cancel();                 // 塗り潰しを解除。次に出すとき opacity:1 に戻る
    prev.style.pointerEvents = "";
  }

  // アニメーションは inline style より優先されるので、開始前の 1 フレームを
  // opacity:0 で押さえておけば全開の状態がちらつかない
  next.style.opacity = "0";
  next.hidden = false;
  const into = fade(next, 0, 1);
  await wait(FADE_MS);
  into.cancel();
  next.style.opacity = "";

  return next;
}

/** いま表示中のシーン要素 */
export function currentScene() {
  return current;
}
