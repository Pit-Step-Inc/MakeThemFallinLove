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

/**
 * 画像を1枚読む。
 *
 * **onload だけでは足りない。** onload は「読み終わった」であって
 * 「デコードし終わった」ではない。連番コマの差し替えでは、そのせいで
 * 最初の1枚が一瞬空になることが実際にあった（loadFrameClip 参照）。
 * decode() まで待てば、使うときには必ず絵がある。
 */
async function loadImage(src) {
  const img = new Image();
  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = () => reject(new Error(`failed to load ${src}`));
    img.src = src;
  });
  // 対応していない環境（や失敗）でも読み込み自体は済んでいるので、そのまま返す
  if (img.decode) await img.decode().catch(() => {});
  return img;
}

/**
 * クリップ（JSON + シート画像）を読む。
 *
 * @param {string} character "Martin" | "Catherine"
 * @param {string} clip      "martin_walk" など（拡張子なし）
 * @returns {Promise<object>} JSON の中身に image を足したもの
 */
/** 読んだクリップの置き場。表情ごとに何度も読み直さないため */
const clips = new Map();

export function loadClip(character, clip) {
  const key = `${character}/${clip}`;
  let pending = clips.get(key);
  if (!pending) {
    pending = fetchClip(character, clip);
    // 失敗を握ったままにすると二度と読み直せなくなる
    pending.catch(() => clips.delete(key));
    clips.set(key, pending);
  }
  return pending;
}

async function fetchClip(character, clip) {
  const dir = `${CLIP_ROOT}/${character}`;

  const res = await fetch(`${dir}/${clip}.json`);
  if (!res.ok) throw new Error(`${clip}.json: ${res.status} ${res.statusText}`);
  const data = await res.json();

  const image = await loadImage(`${dir}/${data.sheet}`);
  return { ...data, image };
}

/**
 * 経過時間から何コマ目かを出す。
 *
 * **負の経過時間を 0 に切り上げるのが肝。** start() は
 * performance.now() を開始時刻にするが、rAF が渡してくる now は
 * **そのフレームの開始時刻**なので、start() を呼んだ瞬間より前に
 * なることがある。そのまま計算すると剰余が負になり（JS の % は
 * 負を返す）、frames[-1] が undefined、描画座標が NaN になって
 * 1コマぶん何も描かれない。表情を切り替えた直後にだけ白く光るのは
 * これが原因だった。
 */
function frameAt(now, startedAt, fps, length) {
  const elapsed = Math.max(0, now - startedAt);
  return Math.floor((elapsed / 1000) * fps) % length;
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

  /**
   * コマを1枚描く。
   *
   * **番号が取れていないときは何もしない。** clearRect のあとに
   * drawImage が座標 NaN で呼ばれると、例外も出ないまま何も描かれず、
   * キャンバスが空のまま1コマ進んでしまう（＝背景が透けて白く光る）。
   */
  function drawFrame(index) {
    if (!Number.isFinite(index) || index === shown) return;
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
    drawFrame(frames[frameAt(now, startedAt, fps, frames.length)]);
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

/* ---------------------------------------------------------------
   連番 PNG のクリップ（scene_change 用）

   scene_change は 1コマ 1672x941 あり、1枚のシートにすると
   13376x3764 ＝ 5000万画素になるのでシートが用意されていない
   （develop/scene_change/README.md）。frameDir の連番 PNG を
   そのまま <img> に差し替えて回す。
   --------------------------------------------------------------- */

const FRAME_ROOT = "assets/blender/develop";

/**
 * 連番コマのクリップを読む。全コマのデコードまで待つので、
 * 再生を始めた直後に白コマが出ない。
 *
 * @param {string} dir  "scene_change" など CLIP_ROOT 直下の名前
 * @param {string} clip JSON のファイル名（拡張子なし）
 */
export async function loadFrameClip(dir, clip) {
  const base = `${FRAME_ROOT}/${dir}`;

  const res = await fetch(`${base}/${clip}.json`);
  if (!res.ok) throw new Error(`${clip}.json: ${res.status} ${res.statusText}`);
  const data = await res.json();

  const pad = (i) => String(i).padStart(2, "0");
  const urls = Array.from(
    { length: data.frameCount },
    (_, i) => `${base}/${data.frameDir}/${data.framePattern.replace("%02d", pad(i))}`
  );

  // loadImage が decode() まで待つので、差し替えた瞬間に空になることはない
  const images = await Promise.all(urls.map(loadImage));

  return { ...data, urls, images };
}

/**
 * クリップを <img> に流す。src を差し替えるだけなので、
 * キャンバスと違って 1672x941 を 32 枚ぶん常駐させずに済む。
 *
 * @param {HTMLImageElement} el
 * @param {object} clip loadFrameClip() の戻り値
 */
export function createFrameAnim(el, clip) {
  const { urls, frames, fps } = clip;

  let rafId = 0;
  let startedAt = 0;
  let shown = -1;

  function drawFrame(index) {
    if (index === shown) return;
    shown = index;
    el.src = urls[index];
  }

  function tick(now) {
    rafId = requestAnimationFrame(tick);
    drawFrame(frames[frameAt(now, startedAt, fps, frames.length)]);
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
