// The progress bar: jumps to each milestone, then creeps toward the soft target until the next one.
// Given a run's ``segments`` ({label, start, end} in percent of the run), it's one step per segment, joined, with its
// name inside: the steps the run goes through, ticking off as they finish. One fill grows under them all, so it moves
// on in one place only; the steps are equal on screen, so it reaches the end of each as the run reaches the end of
// that step's share. The fill glides after the run, and the text follows the fill, not the run: a step ticks off as
// the fill crosses its end, the next takes over then, and the step under way says what's happening instead of its
// name (setDetail), with a spinner beside it.

"use strict";

class ProgressBar {
  constructor(root, { segments = null } = {}) {
    this.root = root;
    this.chunk = $(".progress-chunk", root);
    this.segments = [];
    this.detail = null;
    this.shown = 0;    // how far the fill is across the steps, in steps, as it glides after the run
    this.target = 0;   // how far the run is, in steps
    this.gliding = false;
    if (segments) this.setSegments(segments);
    this.value = 0;
    this.timer = null;
  }

  setSegments(segments) {
    this.root.classList.add("segmented");
    this.fill = document.createElement("div");
    this.fill.className = "run-fill";
    this.root.replaceChildren(this.fill);
    this.segments = segments.map(({ label, start, end }) => {
      const element = document.createElement("div");
      element.className = "segment";
      element.innerHTML =
        '<span class="segment-label"><span class="segment-text"></span><span class="spinner"></span></span>';
      $(".segment-text", element).textContent = label;
      this.root.append(element);
      return {
        element, label, start, end,
        text: $(".segment-text", element),
      };
    });
  }

  /** What the step under way says instead of its name (the run's live status), or null for its name. */
  setDetail(detail) {
    this.detail = detail;
    if (this.segments.length) this.render();
  }

  set(value) {
    this.root.classList.toggle("running", value < 100);
    this.value = value;
    this.root.setAttribute("aria-valuenow", String(Math.round(value)));
    if (!this.segments.length) {
      this.chunk.style.width = `${value}%`;
      return;
    }
    this.target = this.segments.reduce(
      (steps, { start, end }) => steps + Math.min(Math.max((value - start) / (end - start), 0), 1), 0,
    );
    if (this.target < this.shown) this.shown = this.target;   // a new run: back to the start at once
    this.render();
    if (!this.gliding && this.shown !== this.target) {
      this.gliding = true;
      this.lastFrame = null;
      requestAnimationFrame((now) => this.glide(now));
    }
  }

  /** One frame of the fill gliding after the run: most of the way in ~120ms, and there in the end. */
  glide(now) {
    const dt = now - (this.lastFrame ?? now);
    this.lastFrame = now;
    const gap = this.target - this.shown;
    this.shown = Math.abs(gap) < 0.002 ? this.target : this.shown + gap * Math.min(1, dt / 120);
    this.render();
    if (this.shown !== this.target) requestAnimationFrame((t) => this.glide(t));
    else this.gliding = false;
  }

  /** The fill where it's got to, and the steps' text from it: done behind it, the one it's in under way. */
  render() {
    const shown = this.shown;
    const runStep = Math.min(Math.floor(this.target), this.segments.length - 1);   // the step the run is in
    this.fill.style.width = `${(shown / this.segments.length) * 100}%`;
    this.segments.forEach((segment, index) => {
      const part = Math.min(Math.max(shown - index, 0), 1);
      const active = part < 1 && shown >= index;
      segment.element.classList.toggle("done", part >= 1);
      segment.element.classList.toggle("active", active);
      // The status is the run's step's: shown once the fill has got there, not on the step it's still finishing.
      segment.text.textContent = active && this.detail && index === runStep ? this.detail : segment.label;
    });
  }

  start() { this.stop(); this.set(0); }
  finish() { this.stop(); this.set(100); }

  /** Back to bare ground, as before the first run: no fill, no ticks, nothing under way. */
  reset() {
    this.stop();
    this.value = this.target = this.shown = 0;
    this.detail = null;
    this.root.classList.remove("running");
    this.root.setAttribute("aria-valuenow", "0");
    if (this.segments.length) this.render();
    else this.chunk.style.width = "0%";
  }

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
