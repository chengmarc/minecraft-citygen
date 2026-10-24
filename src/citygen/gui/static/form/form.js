// The algorithm form, for Preview and for Build: header selectors, the advanced toggle, the grouped knobs.

"use strict";

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
      const [name, tip] = TEXT.form.knobs[spec.name];
      const label = document.createElement("label");
      label.textContent = name;
      label.htmlFor = `${prefix}-${spec.name}`;
      const select = document.createElement("select");
      select.id = label.htmlFor;
      select.title = tip;
      const words = TEXT.form.options[spec.name];
      for (const value of spec.options) select.add(new Option(words[value] ?? value, value));
      select.addEventListener("change", onChange);
      const field = document.createElement("div");
      field.className = "select-field";
      field.append(label, select);
      $(".selectors", root).append(field);
      this.fields[spec.name] = { get: () => select.value, set: (v) => { select.value = v; } };
    }

    for (const group of form.groups) {
      const fieldset = document.createElement("fieldset");
      fieldset.setAttribute("aria-label", TEXT.form.groups[group.code]);   // no heading shown: named for screen readers
      for (const spec of group.fields) fieldset.append(this.buildRow(prefix, spec, onChange));
      $(".advanced-inner", this.panel).append(fieldset);
    }
  }

  buildRow(prefix, spec, onChange) {
    const row = document.createElement("div");
    row.className = "form-row";
    const [name, tip] = TEXT.form.knobs[spec.name];
    row.title = tip;
    const label = document.createElement("label");
    label.textContent = name;
    label.htmlFor = `${prefix}-${spec.name}`;
    row.append(label);

    if (spec.kind === "text") {
      const input = document.createElement("input");
      input.type = "text";
      input.id = label.htmlFor;
      input.placeholder = TEXT.form.placeholders[spec.name] ?? "";
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
    $("span", this.toggle).textContent = visible ? TEXT.form.fewer : TEXT.form.more;
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
