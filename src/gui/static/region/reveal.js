// The region map's chunks popping in as the engine draws it (region.js), over the map's viewer.

"use strict";

// A strip pops in over as long as the engine took to draw it (the time between its picture and the one before), so
// the map keeps pace with the drawing at any speed. These are the strip's shape, as shares of that time: each chunk's
// pop, and the spread of their starts across the strip, down it, and at random. They add up to the whole.
const POP_SHARE = 0.4;
const ACROSS_SHARE = 0.35;
const DOWN_SHARE = 0.15;
const JITTER_SHARE = 0.1;
// Never so quick it flashes, never so slow a stalled draw makes it crawl.
const STRIP_MIN_MS = 200;
const STRIP_MAX_MS = 2000;

/** The map's chunks popping in as it's drawn, like Extract's pieces. The map is transparent where there's no world,
 *  so the picture showing can't hide the next one: it stays the previous picture while a canvas over it, inside the
 *  zoomed layer, grows and fades each newly drawn chunk in; then the caller swaps the picture and ends the canvas. */
class ChunkReveal {
  constructor(viewer) {
    this.viewer = viewer;
    this.canvas = null;
    this.frame = 0;
  }

  /** Pop ``after``'s chunks (``tile`` px squares) in, over rows ``fromRow``..``toRow``. Resolves when they're all in,
   *  with the canvas still up: ``finish()`` takes it down, once the picture under it shows ``after``. */
  play(after, fromRow, toRow, tile, duration) {
    this.finish();
    if (toRow <= fromRow || matchMedia("(prefers-reduced-motion: reduce)").matches) return Promise.resolve();
    const done = new Promise((resolve) => { this.resolve = resolve; });
    const width = after.naturalWidth;
    const canvas = document.createElement("canvas");
    canvas.className = "viewer-reveal";
    canvas.width = width;
    canvas.height = after.naturalHeight;
    this.viewer.layer.insertBefore(canvas, this.viewer.overlay);
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");

    // A wave across the band, from its top left to its bottom right: down it, and left to right along each row, each
    // chunk a little early or late, so it ripples in.
    const tiles = [];
    const bandRows = Math.max(1, Math.ceil((toRow - fromRow) / tile));
    for (let y = fromRow; y < toRow; y += tile) {
      for (let x = 0; x < width; x += tile) {
        const down = (y - fromRow) / tile / bandRows;
        const across = x / width;
        const delay = (down * DOWN_SHARE + across * ACROSS_SHARE + Math.random() * JITTER_SHARE) * duration;
        tiles.push({ x, y, w: Math.min(tile, width - x), h: Math.min(tile, toRow - y), delay });
      }
    }

    const start = performance.now();
    const step = (now) => {
      let pending = 0;
      for (const t of tiles) {
        if (t.done) continue;
        const p = Math.min(Math.max((now - start - t.delay) / (POP_SHARE * duration), 0), 1);
        if (p === 0) {
          pending += 1;
          continue;
        }
        const e = 1 - (1 - p) ** 3;   // ease out
        const s = 0.6 + 0.4 * e;
        ctx.clearRect(t.x, t.y, t.w, t.h);
        ctx.globalAlpha = e;
        ctx.drawImage(after, t.x, t.y, t.w, t.h, t.x + (t.w * (1 - s)) / 2, t.y + (t.h * (1 - s)) / 2, t.w * s, t.h * s);
        ctx.globalAlpha = 1;
        if (p >= 1) t.done = true;
        else pending += 1;
      }
      if (pending) {
        this.frame = requestAnimationFrame(step);
      } else {
        this.resolve?.();
        this.resolve = null;
      }
    };
    this.frame = requestAnimationFrame(step);
    return done;
  }

  /** Take the canvas down: at the end of a band, or at once (the dialog opened again, an error). */
  finish() {
    cancelAnimationFrame(this.frame);
    this.canvas?.remove();
    this.canvas = null;
    this.resolve?.();
    this.resolve = null;
  }
}
