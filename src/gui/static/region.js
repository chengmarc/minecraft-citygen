// The region map: the world from above, where Shift+drag selects an area snapped to whole chunks.
// The preview's ``meta`` maps its pixels to blocks: block x0..x1 and z0..z1, ``step`` blocks per pixel.

"use strict";

const CHUNK_SIZE = 16;

class RegionMap {
  constructor(dialog, api) {
    this.dialog = dialog;
    this.api = api;
    this.viewer = new ImageViewer($(".viewer", dialog));
    this.viewer.interceptPointer = (event) => this.onPointerDown(event);
    this.status = $(".status", dialog);
    this.progress = new ProgressBar($(".progress", dialog));
    this.applyButton = $('[data-action="apply"]', dialog);
    this.meta = null;
    this.selection = null;   // [[x, y, z], [x, y, z]] in blocks
    this.onApply = null;

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
    this.applyButton.disabled = true;
    this.viewer.reset();
    this.viewer.setOverlay(null);
    this.status.textContent = "Loading world preview...";
    this.progress.root.hidden = false;
    this.progress.indeterminate();
    this.dialog.showModal();   // before asking: a cached map can answer at once
    const answer = await this.api.load_world_map();
    if (answer.error) {
      this.dialog.close();
      showError(answer.error);
    }
  }

  /** A ``worldMap`` event: render progress, then the map or why it failed. */
  receive(payload) {
    if (!this.dialog.open) return;
    if (payload.error) {
      this.progress.root.hidden = true;
      this.viewer.setMessage(payload.error);
      this.status.textContent = payload.error;
    } else if (payload.src) {
      this.progress.root.hidden = true;
      this.meta = payload.meta;
      this.viewer.load(payload).then((shown) => {
        if (shown) this.selectWorld(this.bounds.start, this.bounds.end);   // the status then reads the selection
      });
    } else {
      this.progress.set((payload.completed / Math.max(payload.total, 1)) * 100);
    }
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
