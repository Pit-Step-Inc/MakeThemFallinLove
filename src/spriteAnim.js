/**
 * スプライトシートのアニメーション再生
 *
 * 素材は assets/blender/develop/<キャラ>/ にある
 * 「横1列のPNGシート + タイムライン入りJSON」の組。
 * JSON の frames は「1フレーム=1要素」に展開済みなので、
 * 経過時間から出した index でそのまま引ける。
 *
 * 【重要】コマの寸法はクリップごとに違う
 * frameWidth / frameHeight を決め打ちせず、必ず JSON の値を使うこと
 * （walk は全身、表情クリップはバストアップで、幅が 234〜576 とばらつく）。
 *
 * 【重要】GIF ではなく PNG シートを使う
 * assets/blender/gifまとめ/ の GIF は共有用。透過が2値に潰れていて
 * 縁が汚れるうえ、黒背景に置くと明るい矩形の板が出る。
 *
 * 【重要】進行の判断に rAF を使わない
 * タブが裏に回ると rAF は止まる。ここは見た目の飾りに徹していて、
 * シーン遷移のタイミングは持たない（scenes.js 冒頭に同じ理由のメモあり）。
 */

const CLIP_ROOT = "assets/blender/develop";

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`failed to load ${src}`));
    img.src = src;
  });
}

/**
 * クリップ（JSON + シート画像）を読む。
 *
 * @param {string} character "Martin" | "Catherine"
 * @param {string} clip      "martin_walk" など（拡張子なし）
 * @returns {Promise<object>} JSON の中身に image を足したもの
 */
export async function loadClip(character, clip) {
  const dir = `${CLIP_ROOT}/${character}`;

  const res = await fetch(`${dir}/${clip}.json`);
  if (!res.ok) throw new Error(`${clip}.json: ${res.status} ${res.statusText}`);
  const data = await res.json();

  const image = await loadImage(`${dir}/${data.sheet}`);
  return { ...data, image };
}

/**
 * クリップを <canvas> に流す。
 *
 * canvas の解像度はコマの原寸に合わせ、拡大縮小は CSS 側に任せる
 * （style.css の .walker が image-rendering: pixelated を掛けている）。
 *
 * @param {HTMLCanvasElement} canvas
 * @param {object} clip loadClip() の戻り値
 */
export function createSpriteAnim(canvas, clip) {
  const { image, frameWidth, frameHeight, frames, fps } = clip;

  canvas.width = frameWidth;
  canvas.height = frameHeight;

  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  let rafId = 0;
  let startedAt = 0;
  let shown = -1;

  function drawFrame(index) {
    if (index === shown) return;
    shown = index;
    ctx.clearRect(0, 0, frameWidth, frameHeight);
    ctx.drawImage(
      image,
      index * frameWidth, 0, frameWidth, frameHeight,
      0, 0, frameWidth, frameHeight
    );
  }

  function tick(now) {
    rafId = requestAnimationFrame(tick);
    // 裏に回って復帰すると now が大きく飛ぶが、剰余で吸収される
    const f = Math.floor(((now - startedAt) / 1000) * fps) % frames.length;
    drawFrame(frames[f]);
  }

  return {
    /** ループ再生を始める。多重に呼んでも増殖しない */
    start() {
      if (rafId) return;
      startedAt = performance.now();
      rafId = requestAnimationFrame(tick);
    },

    stop() {
      if (!rafId) return;
      cancelAnimationFrame(rafId);
      rafId = 0;
    },

    /** 動かさずに1コマだけ出す（prefers-reduced-motion 用） */
    pose(index = frames[0]) {
      this.stop();
      drawFrame(index);
    },
  };
}
