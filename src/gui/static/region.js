// The region map: the world from above, where Shift+drag selects an area snapped to whole chunks.
// The preview's ``meta`` maps its pixels to blocks: block x0..x1 and z0..z1, ``step`` blocks per pixel.

"use strict";

const CHUNK_SIZE = 16;
const POP_MS = 300;

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
  play(after, fromRow, toRow, tile) {
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

    // Roughly top to bottom across the band, each chunk a little early or late, so it ripples in.
    const tiles = [];
    const bandRows = Math.max(1, Math.ceil((toRow - fromRow) / tile));
    for (let y = fromRow; y < toRow; y += tile) {
      for (let x = 0; x < width; x += tile) {
        const order = (y - fromRow) / tile / bandRows;
        tiles.push({ x, y, w: Math.min(tile, width - x), h: Math.min(tile, toRow - y), delay: order * 260 + Math.random() * 160 });
      }
    }

    const start = performance.now();
    const step = (now) => {
      let pending = 0;
      for (const t of tiles) {
        if (t.done) continue;
        const p = Math.min(Math.max((now - start - t.delay) / POP_MS, 0), 1);
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

/** A transparent picture the map's size, for the view and the selection to be set up on before any chunk is in. */
function blankPicture(width, height) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas.toDataURL();
}

class RegionMap {
  constructor(dialog, api) {
    this.dialog = dialog;
    this.api = api;
    this.viewer = new ImageViewer($(".viewer", dialog));
    this.viewer.interceptPointer = (event) => this.onPointerDown(event);
    this.status = $(".foot-info > .status", dialog);
    // The same run bar as the tabs', in the footer in the selection's place while the map is being drawn (a cached
    // one opens at once): the footer is the buttons' height either way, so the map never changes size under it.
    this.runbar = $(".runbar", dialog);
    this.progress = new ProgressBar($(".progress", this.runbar), { percent: $(".percent", this.runbar) });
    $(".status", this.runbar).textContent = TEXT.mapDrawing;
    this.applyButton = $('[data-action="apply"]', dialog);
    this.meta = null;
    this.selection = null;   // [[x, y, z], [x, y, z]] in blocks
    this.onApply = null;
    this.reveal = new ChunkReveal(this.viewer);
    this.frames = Promise.resolve();   // the map's pictures, shown one after another
    this.drawn = 0;                    // how far down it's drawn, from 0 to 1
    this.opening = 0;                  // which opening of the dialog the pictures belong to

    $('[data-action="cancel"]', dialog).addEventListener("click", () => dialog.close());
    this.applyButton.addEventListener("click", () => {
      if (!this.selection) return;
      this.onApply(...this.selection);
      dialog.close();
    });
    dialog.addEventListener("close", () => { this.onApply = null; });
  }

  /** Open on ``bounds`` ({start, end} in blocks); ``onApply(start, end)`` gets the chosen area. */
  async open(title, bounds, onApply) {
    $("h2", this.dialog).textContent = title;
    this.bounds = bounds;
    this.onApply = onApply;
    this.meta = null;
    this.selection = null;
    this.opening += 1;
    this.reveal.finish();
    this.drawn = 0;
    this.applyButton.disabled = true;
    this.viewer.reset();
    this.viewer.setOverlay(null);
    this.status.textContent = TEXT.mapLoading;
    this.runbar.classList.remove("active");
    this.progress.start();
    this.dialog.showModal();   // before asking: a cached map can answer at once
    const answer = await this.api.load_world_map();
    if (answer.error) {
      this.dialog.close();
      showError(describeError(answer.error, "extract"));
    }
  }

  /** A ``worldMap`` event: drawing progress, the map so far (``partial``) while it's drawn, then the map; or why
   *  there isn't one. The area can be chosen from the first picture on: later ones keep the view and the choice. */
  receive(payload) {
    if (!this.dialog.open) return;
    if ("error" in payload || "missing" in payload) {
      const message = "missing" in payload ? TEXT.mapMissing(payload.missing) : payload.error || TEXT.mapFailed;
      this.reveal.finish();
      this.runbar.classList.remove("active");
      this.viewer.setMessage(message);
      this.status.textContent = message;
    } else if (payload.src) {
      const first = !this.meta;
      this.meta = payload.meta;
      if (!payload.partial) {
        this.progress.finish();
        this.runbar.classList.remove("active");
      }
      if (first && !payload.partial) {   // a cached map: all of it, at once
        this.viewer.load(payload).then((shown) => {
          if (shown) this.selectWorld(this.bounds.start, this.bounds.end);   // the status reads it
        });
      } else {
        // Fetched now, as it's announced; shown in its turn, after the band before it has popped in.
        const picture = new Image();
        picture.src = payload.src;
        const ready = picture.decode().then(() => picture, () => null);
        const opening = this.opening;
        this.frames = this.frames.then(() => this.showFrame(payload, ready, first, opening));
      }
    } else {
      this.runbar.classList.add("active");
      this.progress.set((payload.completed / Math.max(payload.total, 1)) * 100);
    }
  }

  /** One more picture of the map being drawn: the newly drawn rows' chunks pop in, the next picture waiting until
   *  they're all in. The view and the selection stay. */
  async showFrame(payload, ready, first, opening) {
    const next = await ready;
    if (!next || !this.dialog.open || opening !== this.opening) return;
    const drawn = payload.partial ? payload.drawn : 1;
    const tile = Math.max(8, Math.round(CHUNK_SIZE / this.meta.step));
    const height = next.naturalHeight;
    const row = (fraction) => (fraction >= 1 ? height : Math.min(height, Math.round((fraction * height) / tile) * tile));
    if (first) {   // the map's size, nothing in it yet: fitted, with the area's box on it, before the first chunks pop in
      await this.viewer.load({ src: blankPicture(next.naturalWidth, height) });
      if (!this.selection) this.selectWorld(this.bounds.start, this.bounds.end);
    }
    await this.reveal.play(next, row(this.drawn), row(drawn), tile);
    if (opening !== this.opening) return;
    this.viewer.img.src = payload.src;              // the whole new picture, the same as the canvas over it shows
    await this.viewer.img.decode().catch(() => {});
    this.reveal.finish();
    this.drawn = drawn;
  }

  chunkAt(event) {
    const { x0, z0, x1, z1, step } = this.meta;
    const point = this.viewer.toImage(event);
    const worldX = x0 + Math.min(Math.floor(point.x * step), x1 - x0);
    const worldZ = z0 + Math.min(Math.floor(point.y * step), z1 - z0);
    return [Math.floor(worldX / CHUNK_SIZE), Math.floor(worldZ / CHUNK_SIZE)];
  }

  /** Shift+drag selects; a plain drag is left to the viewer, to pan. */
  onPointerDown(event) {
    if (!event.shiftKey || !this.meta) return false;
    const root = this.viewer.root;
    const first = this.chunkAt(event);
    root.setPointerCapture(event.pointerId);
    this.selectChunks(first, first);
    const move = (e) => this.selectChunks(first, this.chunkAt(e));
    const up = (e) => {
      this.selectChunks(first, this.chunkAt(e));
      root.removeEventListener("pointermove", move);
      root.removeEventListener("pointerup", up);
    };
    root.addEventListener("pointermove", move);
    root.addEventListener("pointerup", up);
    return true;
  }

  /** Select whole chunks from ``first`` to ``second`` (corners, either order), clipped to the map. */
  selectChunks(first, second) {
    const { x0, z0, x1, z1, step } = this.meta;
    const [chunkX0, chunkX1] = [first[0], second[0]].sort((a, b) => a - b);
    const [chunkZ0, chunkZ1] = [first[1], second[1]].sort((a, b) => a - b);
    const worldX0 = Math.max(x0, chunkX0 * CHUNK_SIZE);
    const worldX1 = Math.min(x1, (chunkX1 + 1) * CHUNK_SIZE - 1);
    const worldZ0 = Math.max(z0, chunkZ0 * CHUNK_SIZE);
    const worldZ1 = Math.min(z1, (chunkZ1 + 1) * CHUNK_SIZE - 1);
    // The height range isn't chosen on the map: it stays the area's own.
    this.selection = [
      [worldX0, this.bounds.start[1], worldZ0],
      [worldX1, this.bounds.end[1], worldZ1],
    ];
    this.viewer.setOverlay({
      x: (worldX0 - x0) / step,
      y: (worldZ0 - z0) / step,
      width: (worldX1 + 1 - worldX0) / step,
      height: (worldZ1 + 1 - worldZ0) / step,
    });
    this.applyButton.disabled = false;
    this.status.textContent =
      `Selection: x ${worldX0} to ${worldX1}, z ${worldZ0} to ${worldZ1} ` +
      `(${chunkX1 - chunkX0 + 1} x ${chunkZ1 - chunkZ0 + 1} chunks)`;
  }

  /** Select the chunks a block area covers. */
  selectWorld(start, end) {
    const chunk = (v) => Math.floor(v / CHUNK_SIZE);
    this.selectChunks(
      [chunk(Math.min(start[0], end[0])), chunk(Math.min(start[2], end[2]))],
      [chunk(Math.max(start[0], end[0])), chunk(Math.max(start[2], end[2]))],
    );
  }
}
