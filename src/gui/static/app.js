// The app: three tabs over the numbered pipeline. Python (gui/bridge.py) owns the settings and the runs; the page
// draws them, calls ``window.pywebview.api``, and hears back through ``citygen.receive(event, payload)``.

"use strict";

const citygen = {
  handlers: {},
  receive(event, payload) {
    this.handlers[event]?.(payload);
  },
};
window.citygen = citygen;

/** One tab's run bar (status, percent, progress), its action button, and whether it's running. */
class TabRun {
  constructor(tab, button, step, segments) {
    this.tab = tab;
    this.text = TEXT.tabs[tab];
    const page = $(`#${tab}`);
    this.runbar = $(".runbar", page);
    this.status = $(".status", this.runbar);
    this.progress = new ProgressBar($(".progress", this.runbar), { percent: $(".percent", this.runbar), segments });
    this.button = button;
    this.step = step;
    this.running = false;
    this.ready = false;
  }

  /** Whether the run can start, from Python: Extract needs its world and areas, the others the assets. */
  setGate(ready) {
    this.ready = ready;
    this.refresh();
  }

  refresh() {
    this.button.disabled = this.running || !this.ready;
    this.button.title = this.ready ? this.text.ready : this.text.blocked;
  }

  /** Call ``start()``, which answers ``{error}`` if the run couldn't start. */
  async run(start) {
    this.running = true;
    this.refresh();
    const answer = await start();
    if (answer && answer.error) {
      this.running = false;
      this.refresh();
      showError(describeError(answer.error, this.tab));
    }
    return answer || {};
  }

  /** A ``progress`` event: the first starts the run; the status names the step, from the pipeline or the bar. */
  progressEvent(payload) {
    this.runbar.classList.add("active");
    if (!("detail" in payload)) {
      this.progress.start();
      this.status.textContent = this.text.preparing;
      return;
    }
    this.progress.milestone(payload);
    this.status.textContent = payload.detail || this.text.steps[this.progress.activeIndex] || this.text.preparing;
  }

  done() {
    this.progress.finish();
    this.status.textContent = this.text.done;
    this.step.classList.add("done");
  }

  failed(payload) {
    const failure = describeFailure(this.tab, payload.detail);
    this.status.textContent = failure.title;
    showError(failure);
  }

  finished() {
    this.progress.stop();
    this.running = false;
    this.refresh();
  }
}

function setUpTabs() {
  const tabs = $$(".step");
  for (const tab of tabs) {
    tab.addEventListener("click", () => {
      for (const other of tabs) {
        const selected = other === tab;
        other.setAttribute("aria-selected", String(selected));
        $(`#${other.dataset.tab}`).hidden = !selected;
      }
    });
  }
}

async function start() {
  const api = window.pywebview.api;
  const boot = await api.bootstrap();
  setUpTabs();

  const viewers = Object.fromEntries(
    ["roads", "builds", "grid", "city-preview", "city-render"].map((name) => [name, new ImageViewer($(`#viewer-${name}`))]),
  );
  const steps = Object.fromEntries($$(".step").map((step) => [step.dataset.tab, step]));
  const runs = {
    extract: new TabRun("extract", $("#extract-button"), steps.extract, boot.segments.extract),
    preview: new TabRun("preview", $('#preview [data-action="run"]'), steps.preview, boot.segments.preview),
    build: new TabRun("build", $('#build [data-action="run"]'), steps.build, boot.segments.build),
  };
  const setGates = (gates) => {
    for (const [tab, ready] of Object.entries(gates)) runs[tab].setGate(ready);
    steps.extract.classList.toggle("done", gates.preview);   // the extracted assets are there
  };

  // --- Extract
  const worldPath = $("#world-path");
  const sourceVersion = $("#source-version");
  const targetVersion = $("#target-version");
  const regionMap = new RegionMap($("#region-dialog"), api);

  const showExtraction = ({ extraction, gates }) => {
    if (document.activeElement !== worldPath) worldPath.value = extraction.worldPath;
    sourceVersion.value = extraction.sourceVersion;
    targetVersion.replaceChildren(...extraction.versions.map(({ label, value }) => new Option(label, value)));
    targetVersion.value = extraction.targetVersion;
    for (const card of $$(".area-card")) {
      const { chunks } = extraction.areas[card.dataset.area];
      const chip = $(".chip", card);
      chip.textContent = TEXT.areaChip(Boolean(chunks));
      chip.classList.toggle("selected", Boolean(chunks));
      $(".area-detail", card).textContent = TEXT.area(chunks);
      $("button", card).disabled = !extraction.worldReady;
    }
    setGates(gates);
  };
  showExtraction(boot);

  let worldTimer = null;
  worldPath.addEventListener("input", () => {
    clearTimeout(worldTimer);
    worldTimer = setTimeout(async () => showExtraction(await api.set_world_path(worldPath.value)), 300);
  });
  worldPath.addEventListener("blur", async () => {
    clearTimeout(worldTimer);
    showExtraction(await api.set_world_path(worldPath.value));
  });
  targetVersion.addEventListener("change", async () => showExtraction(await api.set_target_version(targetVersion.value)));

  $("#browse-button").addEventListener("click", async () => {
    const answer = await api.browse_world();
    if (answer.warning) showError(describeError(answer.warning, "extract"));
    if (answer.changed) {   // a new world: its artifacts were cleared, so nothing is done yet
      worldPath.value = answer.extraction.worldPath;
      viewers.roads.reset();
      viewers.builds.reset();
      runs.extract.runbar.classList.remove("active");
      steps.preview.classList.remove("done");
      steps.build.classList.remove("done");
    }
    showExtraction(answer);
  });

  for (const card of $$(".area-card")) {
    const key = card.dataset.area;
    $("button", card).addEventListener("click", async () => {
      const bounds = await api.area_bounds(key);
      regionMap.open(TEXT.areaTitles[key], bounds, async (start, end) => showExtraction(await api.set_area(key, start, end)));
    });
  }

  runs.extract.button.addEventListener("click", () => runs.extract.run(() => api.run_extract()));

  // --- Preview and Build: two forms over one saved state, so the city you preview is the one you build.
  let saveTimer = null;
  const forms = {};
  const changed = (source) => () => {
    const state = forms[source].state();
    for (const [name, form] of Object.entries(forms)) if (name !== source) form.setState(state);
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => api.save_algo(state), 150);
  };
  for (const tab of ["preview", "build"]) {
    forms[tab] = new AlgoControls($(`#${tab} .algo-controls`), boot.form, changed(tab));
    forms[tab].setState(boot.algo);
  }
  const setAlgoState = (state) => Object.values(forms).forEach((form) => form.setState(state));

  $('#preview [data-action="reset"]').addEventListener("click", async () => setAlgoState(await api.reset_algo()));
  runs.preview.button.addEventListener("click", async () => {
    clearTimeout(saveTimer);
    const answer = await runs.preview.run(() => api.run_preview(forms.preview.state()));
    if (answer.state) setAlgoState(answer.state);   // the new seed
  });

  runs.build.button.addEventListener("click", () => {
    clearTimeout(saveTimer);
    runs.build.run(() => api.run_build(forms.build.state()));
  });
  $('#build [data-action="worlds"]').addEventListener("click", async () => {
    const answer = await api.open_worlds_folder();
    if (answer.error) showError(describeError(answer.error, "build"));
  });

  // --- What the runs report
  const shows = {
    extract: { roads: viewers.roads, builds: viewers.builds },
    preview: { grid: viewers.grid, city: viewers["city-preview"] },
    build: { city: viewers["city-render"] },
  };
  Object.assign(citygen.handlers, {
    progress: (payload) => runs[payload.tab].progressEvent(payload),
    done: (payload) => {
      for (const [name, image] of Object.entries(payload.images)) shows[payload.tab][name].load(image);
      runs[payload.tab].done();
    },
    failed: (payload) => runs[payload.tab].failed(payload),
    finished: (payload) => {
      runs[payload.tab].finished();
      setGates(payload.gates);
    },
    worldMap: (payload) => regionMap.receive(payload),
  });
}

window.addEventListener("pywebviewready", start);
