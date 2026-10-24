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
      '<div class="viewer-layer" hidden><img alt="" draggable="false"><div class="viewer-overlay" hidden></div></div>' +
      '<p class="viewer-placeholder"></p>';
    this.layer = $(".viewer-layer", root);
    this.img = $("img", root);
    this.overlay = $(".viewer-overlay", root);
    this.placeholder = $(".viewer-placeholder", root);
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
    this.layer.hidden = true;
    this.img.removeAttribute("src");
    this.root.classList.remove("has-image");
    this.placeholder.textContent = message;
    this.placeholder.hidden = false;
  }

  reset() {
    this.setMessage(this.root.dataset.message || "");
  }

  /** Show ``{src}``, or ``{message}`` in its place; resolves once it's on screen. */
  load(payload) {
    if (!payload.src) {
      this.setMessage(payload.message);
      return Promise.resolve(false);
    }
    return new Promise((resolve) => {
      this.img.onload = () => {
        this.placeholder.hidden = true;
        this.layer.hidden = false;
        this.root.classList.add("has-image");
        this.fit();
        resolve(true);
      };
      this.img.onerror = () => {
        this.setMessage(`Failed to load image:\n${payload.src}`);
        resolve(false);
      };
      this.img.src = payload.src;
    });
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

  // Same steps as before: 1.12x per wheel notch, from -12 to +40 notches.
  onWheel(event) {
    event.preventDefault();
    if (!this.hasImage() || event.deltaY === 0) return;
    const next = Math.min(Math.max(this.zoomLevel - event.deltaY / 100, -12), 40);
    if (next === this.zoomLevel) return;
    const factor = 1.12 ** (next - this.zoomLevel);
    const rect = this.root.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
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
class ProgressBar {
  constructor(root) {
    this.root = root;
    this.chunk = $(".progress-chunk", root);
    this.value = 0;
    this.timer = null;
  }

  set(value) {
    this.root.classList.remove("indeterminate");
    this.value = value;
    this.chunk.style.width = `${value}%`;
    this.root.setAttribute("aria-valuenow", String(Math.round(value)));
  }

  indeterminate() {
    this.stop();
    this.chunk.style.width = "";
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
    this.toggle = $(".toggle", root);
    this.panel = $(".advanced", root);
    this.toggle.addEventListener("click", () => {
      this.setAdvanced(this.toggle.getAttribute("aria-pressed") !== "true");
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
      $(".selectors", root).append(label, select);
      this.fields[spec.name] = { get: () => select.value, set: (v) => { select.value = v; } };
    }

    for (const group of form.groups) {
      const fieldset = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = group.title;
      fieldset.append(legend);
      for (const spec of group.fields) fieldset.append(this.buildRow(prefix, spec, onChange));
      this.panel.append(fieldset);
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
    input.addEventListener("input", () => { output.value = input.value; onChange(); });
    row.append(slider);
    this.fields[spec.name] = {
      get: () => input.value,
      set: (v) => { input.value = v; output.value = input.value; },
    };
    return row;
  }

  setAdvanced(visible) {
    this.toggle.setAttribute("aria-pressed", String(visible));
    this.toggle.textContent = visible ? "Advanced Settings" : "Basic Settings";
    this.panel.hidden = !visible;
  }

  state() {
    const algo = {};
    for (const [name, field] of Object.entries(this.fields)) algo[name] = field.get();
    return { advanced: this.toggle.getAttribute("aria-pressed") === "true", seed: this.seed, algo };
  }

  setState(state) {
    this.setAdvanced(Boolean(state.advanced));
    this.seed = String(state.seed ?? "");
    for (const [name, field] of Object.entries(this.fields)) {
      if (state.algo && name in state.algo) field.set(state.algo[name]);
    }
  }
}
