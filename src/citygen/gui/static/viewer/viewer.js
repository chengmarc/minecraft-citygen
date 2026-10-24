// The image viewer: wheel to zoom about the cursor, drag to pan, double-click to fit. The image and an optional
// overlay share one transformed layer, so the overlay is placed in image pixels and follows every zoom and pan.

"use strict";

const ZOOM_STEP = 1.12;   // each notch of the wheel

class ImageViewer {
  constructor(root) {
    this.root = root;
    this.root.innerHTML =
      '<div class="viewer-canvas"><div class="viewer-layer" hidden>' +
      '<img alt="" draggable="false"><div class="viewer-overlay" hidden></div></div></div>' +
      '<div class="viewer-placeholder"><i class="icon"></i><p></p></div>' +
      '<span class="viewer-caption"></span>' +
      '<div class="viewer-tools"><button type="button" data-zoom="-1">\u2212</button><output></output>' +
      '<button type="button" data-zoom="1">+</button></div>';
    this.layer = $(".viewer-layer", root);
    this.img = $("img", root);
    this.overlay = $(".viewer-overlay", root);
    this.placeholder = $(".viewer-placeholder", root);
    this.zoomReadout = $(".viewer-tools output", root);
    $(".viewer-caption", root).textContent = root.dataset.caption || "";
    if (root.dataset.icon) $(".viewer-placeholder .icon", root).classList.add(`icon-${root.dataset.icon}`);
    for (const button of $$(".viewer-tools button", root)) {
      button.addEventListener("pointerdown", (event) => event.stopPropagation());   // not a pan
      button.addEventListener("dblclick", (event) => event.stopPropagation());
      button.title = Number(button.dataset.zoom) > 0 ? TEXT.zoomIn : TEXT.zoomOut;
      button.addEventListener("click", () => this.zoomBy(Number(button.dataset.zoom) * 2));
    }
    this.interceptPointer = null;   // (event) => true to take a press away from panning
    // data-bounded="width" or "height": the picture fills the viewer that way at the least, and can't be dragged off
    // into empty space. Unbounded, it fits whole, and can be zoomed out past that and dragged anywhere. See limits().
    this.bounded = root.dataset.bounded || null;
    this.fitted = true;   // at the base view, so a resize fits it again
    this.scale = 1;
    this.x = 0;
    this.y = 0;
    this.overlayRect = null;
    this.setMessage(root.dataset.message || "");

    root.addEventListener("wheel", (event) => this.onWheel(event), { passive: false });
    root.addEventListener("pointerdown", (event) => this.onPointerDown(event));
    root.addEventListener("dblclick", () => this.fit());
    new ResizeObserver(() => {
      if (this.fitted) this.fit();
      else if (this.hasImage()) this.apply();   // bounded, it's held inside the new size
    }).observe(root);
  }

  setMessage(message) {
    this.clearGallery();
    this.root.classList.remove("blueprint");
    this.size = null;
    this.layer.hidden = true;
    this.img.removeAttribute("src");
    this.root.classList.remove("has-image");
    $("p", this.placeholder).textContent = message;
    this.placeholder.hidden = false;
  }

  reset() {
    this.setMessage(this.root.dataset.message || "");
  }

  /** Show ``{src}``, or say it's ``{missing}``; resolves once it's on screen. A ``blueprint`` image is a faded
   *  stand-in, a scan sweeping over it, until the real one replaces it.
   *
   *  A picture the size of the one showing (the next preview, the same layout drawn again) swaps in where it is,
   *  keeping the zoom and the pan; another size is fitted to the viewer and fades in. */
  async load(payload) {
    if (!payload.src) {
      this.setMessage(TEXT.imageMissing(payload.missing));
      return false;
    }
    const next = new Image();
    next.src = payload.src;
    try {
      await next.decode();
    } catch {
      this.setMessage(TEXT.imageFailed(payload.src));
      return false;
    }
    const size = { width: next.naturalWidth, height: next.naturalHeight };
    const keepView = this.hasImage() && size.width === this.size.width && size.height === this.size.height;
    this.clearGallery();
    this.root.classList.toggle("blueprint", Boolean(payload.blueprint));
    if (!keepView) this.layer.classList.add("loading");
    this.img.src = payload.src;
    await this.img.decode().catch(() => {});   // decoded already: ready to paint at once
    this.size = size;
    if (keepView) return true;
    this.placeholder.hidden = true;
    this.layer.hidden = false;
    this.root.classList.add("has-image");
    this.fit();
    requestAnimationFrame(() => this.layer.classList.remove("loading"));   // fade the new image in
    return true;
  }

  /** The ``index``-th (from 1) piece a run has rendered, added to a gallery that grows while it renders the rest.
   *  The first piece starts the gallery afresh; the finished image replaces it. */
  addPiece(index, src) {
    if (index === 1 || !this.gallery) {
      this.clearGallery();
      this.gallery = document.createElement("div");
      this.gallery.className = "viewer-gallery";
      this.root.insertBefore(this.gallery, $(".viewer-caption", this.root));
      this.layer.hidden = true;
      this.placeholder.hidden = true;
      this.root.classList.remove("has-image", "blueprint");
    }
    const tile = document.createElement("img");
    tile.alt = "";
    tile.draggable = false;
    tile.src = src;
    this.gallery.append(tile);
    this.gallery.scrollTo({ top: this.gallery.scrollHeight, behavior: "smooth" });   // keep the newest in view
  }

  clearGallery() {
    this.gallery?.remove();
    this.gallery = null;
  }

  hasImage() {
    return !this.layer.hidden && Boolean(this.size);
  }

  imageSize() {
    return this.size;
  }

  /** What the view may be, for this viewer and picture: the one place bounding is decided.
   *
   *  - ``base``: the scale of the base view: across the viewer's width, down its height, or (unbounded) the whole
   *    picture in it;
   *  - ``min`` / ``max``: how far it zooms, from the base: bounded, never smaller; unbounded, 12 notches smaller;
   *    either, 40 notches bigger (1.12x a notch);
   *  - ``hold``: whether the picture's kept inside: centred where it's smaller than the viewer, its edges no further
   *    in than the viewer's where it's bigger. */
  limits() {
    const { clientWidth: w, clientHeight: h } = this.root;
    const { width: iw, height: ih } = this.imageSize();
    const base = { width: w / iw, height: h / ih }[this.bounded] ?? Math.min(w / iw, h / ih);
    return {
      base,
      min: this.bounded ? base : base * ZOOM_STEP ** -12,
      max: base * ZOOM_STEP ** 40,
      hold: Boolean(this.bounded),
    };
  }

  /** The view brought within its limits. */
  constrain() {
    const { min, max, hold } = this.limits();
    this.scale = Math.min(Math.max(this.scale, min), max);
    if (!hold) return;
    const { clientWidth: w, clientHeight: h } = this.root;
    const iw = this.size.width * this.scale;
    const ih = this.size.height * this.scale;
    this.x = iw <= w ? (w - iw) / 2 : Math.min(0, Math.max(w - iw, this.x));
    this.y = ih <= h ? (h - ih) / 2 : Math.min(0, Math.max(h - ih, this.y));
  }

  /** The base view: at the base scale, centred, and from the top when it fills the width (a tall contact sheet is
   *  read by dragging down it). */
  fit() {
    if (!this.hasImage()) return;
    const { clientWidth: w, clientHeight: h } = this.root;
    const { width: iw, height: ih } = this.imageSize();
    this.fitted = true;
    this.scale = this.limits().base;
    this.x = (w - iw * this.scale) / 2;
    this.y = this.bounded === "width" ? 0 : (h - ih * this.scale) / 2;
    this.apply();
  }

  apply() {
    if (this.hasImage()) this.constrain();
    this.layer.style.transform = `translate(${this.x}px, ${this.y}px) scale(${this.scale})`;
    this.overlay.style.borderWidth = `${2 / this.scale}px`;   // a 2px outline at any zoom
    this.zoomReadout.value = `${Math.round(this.scale * 100)}%`;
  }

  /** The image pixel under a pointer, clamped to the image. */
  toImage(event) {
    const rect = this.root.getBoundingClientRect();
    const { width, height } = this.imageSize();
    const ix = (event.clientX - rect.left - this.x) / this.scale;
    const iy = (event.clientY - rect.top - this.y) / this.scale;
    return { x: Math.min(Math.max(ix, 0), width - 1), y: Math.min(Math.max(iy, 0), height - 1) };
  }

  /** Draw ``{x, y, width, height}`` (image pixels) over the image, or nothing for null. */
  setOverlay(rect) {
    this.overlay.hidden = !rect;
    if (!rect) return;
    Object.assign(this.overlay.style, {
      left: `${rect.x}px`, top: `${rect.y}px`, width: `${rect.width}px`, height: `${rect.height}px`,
    });
  }

  // A notch of the wheel at a time, about the cursor.
  onWheel(event) {
    event.preventDefault();
    if (!this.hasImage() || event.deltaY === 0) return;
    const rect = this.root.getBoundingClientRect();
    this.zoomBy(-event.deltaY / 100, event.clientX - rect.left, event.clientY - rect.top);
  }

  /** Zoom by ``notches`` about a point of the viewer (its centre by default), within limits(). */
  zoomBy(notches, mx = this.root.clientWidth / 2, my = this.root.clientHeight / 2) {
    if (!this.hasImage()) return;
    const { min, max } = this.limits();
    const scale = Math.min(Math.max(this.scale * ZOOM_STEP ** notches, min), max);
    if (scale === this.scale) return;
    const factor = scale / this.scale;
    this.fitted = false;
    this.scale = scale;
    this.x = mx - (mx - this.x) * factor;
    this.y = my - (my - this.y) * factor;
    this.apply();
  }

  onPointerDown(event) {
    if (event.button !== 0 || !this.hasImage()) return;
    if (this.interceptPointer && this.interceptPointer(event)) return;
    const startX = event.clientX - this.x;
    const startY = event.clientY - this.y;
    this.root.setPointerCapture(event.pointerId);
    this.root.classList.add("dragging");
    const move = (e) => {
      this.x = e.clientX - startX;
      this.y = e.clientY - startY;
      this.apply();
    };
    const up = () => {
      this.root.classList.remove("dragging");
      this.root.removeEventListener("pointermove", move);
      this.root.removeEventListener("pointerup", up);
    };
    this.root.addEventListener("pointermove", move);
    this.root.addEventListener("pointerup", up);
  }
}
