// The page's building blocks: the image viewer, the progress bar, the algorithm form, and the error dialog.

"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Show the error dialog. */
function showError({ title, message }) {
  const dialog = $("#error-dialog");
  $("h2", dialog).textContent = title;
  $("p", dialog).textContent = message;
  dialog.showModal();
}

// --- Image viewer: wheel to zoom about the cursor, drag to pan, double-click to fit. The image and an optional
// overlay share one transformed layer, so the overlay is placed in image pixels and follows every zoom and pan.
class ImageViewer {
  constructor(root) {
    this.root = root;
    this.root.innerHTML =
      '<div class="viewer-canvas"><div class="viewer-layer" hidden>' +
      '<img alt="" draggable="false"><div class="viewer-overlay" hidden></div></div></div>' +
      '<div class="viewer-placeholder"><i class="icon"></i><p></p></div>' +
      '<span class="viewer-caption"></span>' +
      '<div class="viewer-tools"><button type="button" data-zoom="-1" title="Zoom out">\u2212</button><output></output>' +
      '<button type="button" data-zoom="1" title="Zoom in">+</button>' +
      '<button type="button" data-zoom="fit" title="Fit (or double-click)">Fit</button></div>';
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
      button.addEventListener("click", () => {
        if (button.dataset.zoom === "fit") this.fit();
        else this.zoomBy(Number(button.dataset.zoom) * 2);
      });
    }
    this.interceptPointer = null;   // (event) => true to take a press away from panning
    this.zoomLevel = 0;
    this.scale = 1;
    this.x = 0;
    this.y = 0;
    this.overlayRect = null;
    this.setMessage(root.dataset.message || "");

    root.addEventListener("wheel", (event) => this.onWheel(event), { passive: false });
    root.addEventListener("pointerdown", (event) => this.onPointerDown(event));
    root.addEventListener("dblclick", () => this.fit());
    new ResizeObserver(() => { if (this.zoomLevel === 0) this.fit(); }).observe(root);
  }

  setMessage(message) {
    this.clearGallery();
    this.root.classList.remove("blueprint");
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
   *  stand-in, a scan sweeping over it, until the real one replaces it. */
  load(payload) {
    if (!payload.src) {
      this.setMessage(TEXT.imageMissing(payload.missing));
      return Promise.resolve(false);
    }
    return new Promise((resolve) => {
      this.layer.classList.add("loading");
      this.img.onload = () => {
        this.clearGallery();
        this.root.classList.toggle("blueprint", Boolean(payload.blueprint));
        this.placeholder.hidden = true;
        this.layer.hidden = false;
        this.root.classList.add("has-image");
        this.fit();
        requestAnimationFrame(() => this.layer.classList.remove("loading"));   // fade the new image in
        resolve(true);
      };
      this.img.onerror = () => {
        this.setMessage(`Failed to load image:\n${payload.src}`);
        resolve(false);
      };
      this.img.src = payload.src;
    });
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
    return !this.layer.hidden && this.img.naturalWidth > 0;
  }

  imageSize() {
    return { width: this.img.naturalWidth, height: this.img.naturalHeight };
  }

  fit() {
    if (!this.hasImage()) return;
    const { clientWidth: w, clientHeight: h } = this.root;
    const { width: iw, height: ih } = this.imageSize();
    this.zoomLevel = 0;
    this.scale = Math.min(w / iw, h / ih);
    this.x = (w - iw * this.scale) / 2;
    this.y = (h - ih * this.scale) / 2;
    this.apply();
  }

  apply() {
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

  // 1.12x per wheel notch, from -12 to +40 notches from the fit, about the cursor.
  onWheel(event) {
    event.preventDefault();
    if (!this.hasImage() || event.deltaY === 0) return;
    const rect = this.root.getBoundingClientRect();
    this.zoomBy(-event.deltaY / 100, event.clientX - rect.left, event.clientY - rect.top);
  }

  /** Zoom by ``notches`` about a point of the viewer (its centre by default). */
  zoomBy(notches, mx = this.root.clientWidth / 2, my = this.root.clientHeight / 2) {
    if (!this.hasImage()) return;
    const next = Math.min(Math.max(this.zoomLevel + notches, -12), 40);
    if (next === this.zoomLevel) return;
    const factor = 1.12 ** (next - this.zoomLevel);
    this.zoomLevel = next;
    this.scale *= factor;
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

// --- Progress bar: jumps to each milestone, then creeps toward the soft target until the next one.
// Given a run's ``segments`` ({label, start, end} in percent of the run), it's one labelled track per segment,
// each filling over its own part of the run: the steps the run goes through, ticking off as they finish.
class ProgressBar {
  constructor(root, { percent = null, segments = null } = {}) {
    this.root = root;
    this.percent = percent;
    this.chunk = $(".progress-chunk", root);
    this.segments = [];
    if (segments) this.setSegments(segments);
    this.value = 0;
    this.timer = null;
  }

  setSegments(segments) {
    this.root.classList.add("segmented");
    this.root.replaceChildren();
    this.segments = segments.map(({ label, start, end }) => {
      const element = document.createElement("div");
      element.className = "segment";
      element.innerHTML = '<div class="segment-bar"><div class="segment-fill"></div></div><span class="segment-label"></span>';
      $(".segment-label", element).textContent = label;
      this.root.append(element);
      return { element, fill: $(".segment-fill", element), start, end };
    });
  }

  set(value) {
    this.root.classList.remove("indeterminate");
    this.value = value;
    this.root.setAttribute("aria-valuenow", String(Math.round(value)));
    if (this.percent) this.percent.textContent = `${Math.floor(value)}%`;
    if (!this.segments.length) {
      this.chunk.style.width = `${value}%`;
      return;
    }
    this.activeIndex = -1;   // the segment under way, which the status line names
    this.segments.forEach((segment, index) => {
      const part = Math.min(Math.max((value - segment.start) / (segment.end - segment.start), 0), 1);
      const active = part < 1 && value >= segment.start;
      segment.fill.style.width = `${part * 100}%`;
      segment.element.classList.toggle("done", part >= 1);
      segment.element.classList.toggle("active", active);
      if (active) this.activeIndex = index;
    });
  }

  indeterminate() {
    this.stop();
    if (this.chunk) this.chunk.style.width = "";
    this.root.classList.add("indeterminate");
    this.root.removeAttribute("aria-valuenow");
  }

  start() { this.stop(); this.set(0); }
  finish() { this.stop(); this.set(100); }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
  }

  /** A ``progress`` event from a run: jump to its value (never back), then creep. */
  milestone({ value, softTarget, tickMs, creepRate }) {
    this.stop();
    this.set(Math.max(this.value, value));
    if (softTarget == null) return;
    this.timer = setInterval(() => {
      const remaining = softTarget - this.value;
      if (remaining <= 0) { this.stop(); return; }
      this.set(Math.min(this.value + Math.max(0.2, remaining * creepRate), softTarget));
    }, tickMs);
  }
}

// --- The algorithm form, for Preview and for Build: header selectors, the advanced toggle, the grouped knobs.
class AlgoControls {
  constructor(root, form, onChange) {
    this.fields = {};
    this.seed = "";
    this.toggle = $(".disclosure", root);
    this.panel = $(".advanced", root);
    this.toggle.addEventListener("click", () => {
      this.setAdvanced(this.toggle.getAttribute("aria-expanded") !== "true");
      onChange();
    });

    const prefix = root.closest(".page").id;
    for (const spec of form.selectors) {
      const label = document.createElement("label");
      label.textContent = spec.label;
      label.htmlFor = `${prefix}-${spec.name}`;
      const select = document.createElement("select");
      select.id = label.htmlFor;
      select.title = spec.description;
      for (const option of spec.options) select.add(new Option(option, option));
      select.addEventListener("change", onChange);
      const field = document.createElement("div");
      field.className = "select-field";
      field.append(label, select);
      $(".selectors", root).append(field);
      this.fields[spec.name] = { get: () => select.value, set: (v) => { select.value = v; } };
    }

    for (const group of form.groups) {
      const fieldset = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = group.title;
      fieldset.append(legend);
      for (const spec of group.fields) fieldset.append(this.buildRow(prefix, spec, onChange));
      $(".advanced-inner", this.panel).append(fieldset);
    }
  }

  buildRow(prefix, spec, onChange) {
    const row = document.createElement("div");
    row.className = "form-row";
    row.title = spec.description;
    const label = document.createElement("label");
    label.textContent = spec.label;
    label.htmlFor = `${prefix}-${spec.name}`;
    row.append(label);

    if (spec.kind === "text") {
      const input = document.createElement("input");
      input.type = "text";
      input.id = label.htmlFor;
      input.placeholder = spec.placeholder;
      input.addEventListener("input", onChange);
      row.append(input);
      this.fields[spec.name] = { get: () => input.value.trim(), set: (v) => { input.value = v; } };
      return row;
    }

    const slider = document.createElement("div");
    slider.className = "slider";
    slider.innerHTML = '<div class="slider-track"><input type="range" step="1"></div><output></output>';
    const track = $(".slider-track", slider);
    const input = $("input", slider);
    const output = $("output", slider);
    track.style.setProperty("--ticks", String(spec.max - spec.min));
    input.id = label.htmlFor;
    input.min = spec.min;
    input.max = spec.max;
    const show = () => {
      output.value = input.value;
      input.style.setProperty("--fill", `${((input.value - spec.min) / (spec.max - spec.min)) * 100}%`);
    };
    input.addEventListener("input", () => { show(); onChange(); });
    row.append(slider);
    this.fields[spec.name] = {
      get: () => input.value,
      set: (v) => { input.value = v; show(); },
    };
    return row;
  }

  setAdvanced(visible) {
    this.toggle.setAttribute("aria-expanded", String(visible));
    $("span", this.toggle).textContent = visible ? "Fewer settings" : "More settings";
    this.panel.classList.toggle("open", visible);
    this.panel.inert = !visible;   // closed, its fields can't take focus
  }

  state() {
    const algo = {};
    for (const [name, field] of Object.entries(this.fields)) algo[name] = field.get();
    return { advanced: this.toggle.getAttribute("aria-expanded") === "true", seed: this.seed, algo };
  }

  setState(state) {
    this.setAdvanced(Boolean(state.advanced));
    this.seed = String(state.seed ?? "");
    for (const [name, field] of Object.entries(this.fields)) {
      if (state.algo && name in state.algo) field.set(state.algo[name]);
    }
  }
}
