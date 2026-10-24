// Every word the app shows that isn't in index.html. Python answers with facts and short codes (gui/bridge.py);
// this is where they become text.

"use strict";

const TEXT = {
  tabs: {
    extract: {
      ready: "Extract road, house, and landmark pieces from the selected areas.",
      blocked: "Choose an MC world and all three areas first.",
      preparing: "Preparing extraction",
      failed: "Extract failed",
      running: ["Extract running", "An extraction is already running."],
    },
    preview: {
      ready: "Generate a fast road and city layout preview.",
      blocked: "Complete Extract Assets first.",
      preparing: "Preparing preview",
      failed: "Preview failed",
      running: ["Preview running", "A preview is already running."],
      invalidConfig: "Invalid preview config",
    },
    build: {
      ready: "Build the final schematic, render, and export world.",
      blocked: "Complete Extract Assets first.",
      preparing: "Building city layout",
      failed: "Generation failed",
      running: ["Build running", "A build is already running."],
      invalidConfig: "Invalid city config",
    },
  },
  areaTitles: {
    road: "Choose the road area",
    house: "Choose the house area",
    landmark: "Choose the landmark area",
  },
  area: (chunks) => (chunks ? `${chunks[0]} x ${chunks[1]} chunks` : "No area selected"),
  areaChip: (selected) => (selected ? "Selected" : "Not selected"),
  imageMissing: (path) => `Image not found:\n${path}`,
  imageFailed: (src) => `Failed to load image:\n${src}`,
  zoomIn: "Zoom in",
  zoomOut: "Zoom out",
  mapMissing: (path) => `World preview not found:\n${path}`,
  mapFailed: "Failed to load world preview.",
  mapLoading: "Loading world preview...",
  mapDrawing: "Drawing your world from above. You can already pan, zoom, and choose your area.",
  // The region map's selection: its block corners, and how many chunks it covers.
  selection: ([x0, x1], [z0, z1], [chunksX, chunksZ]) =>
    `Selection: x ${x0} to ${x1}, z ${z0} to ${z1} (${chunksX} x ${chunksZ} chunks)`,
  autoVersion: "Auto",
  // Each run bar's segments, by the codes gui/progress.py gives them.
  segments: {
    extract: {
      scan_roads: "Scan roads",
      road_pieces: "Road pieces",
      road_sheet: "Road sheet",
      scan_builds: "Scan buildings",
      build_pieces: "Building pieces",
      build_sheet: "Building sheet",
    },
    preview: {
      road_pieces: "Road pieces",
      build_pieces: "Building pieces",
      road_layout: "Road layout",
      city_layout: "City layout",
    },
    build: {
      roads: "Roads",
      placement: "Placement",
      buildings: "Buildings",
      schematic: "Schematic",
      render: "Render",
      world: "World",
    },
  },
  // The algorithm form, by the knob names and codes in gui/form.py.
  form: {
    more: "More settings",
    fewer: "Fewer settings",
    knobs: {
      FINE: ["City size", "Changes the footprint of the finished city."],
      GAP_MIXED: ["Road density", "Controls how tightly Avenues and Streets are packed across the city."],
      GAP_BIG: ["Avenue spacing", "Higher values create fewer Avenues."],
      PAD_BIG: ["Avenue edge margin", "Keeps Avenues farther from the edge of the city."],
      GAP_SMALL: ["Street spacing", "Lower values create more Streets."],
      PAD_SMALL: ["Street edge margin", "Keeps Streets farther from the edge of the city."],
      N_BIG_CORNERS: ["Avenue turns", "Adds more bends to Avenues."],
      N_BIG_TEES: ["Avenue T-junctions", "Adds more T-junctions to Avenues."],
      N_SMALL_CORNERS: ["Street turns", "Adds more bends to Streets."],
      N_SMALL_TEES: ["Street T-junctions", "Adds more T-junctions to Streets."],
      BANNED_BUILDINGS: ["Skip building IDs", "Optional comma-separated building IDs to leave out of generation."],
      TYPE1_TOP_FIT_CHOICES: ["House style variety", "Higher values mix in more different standard house designs."],
      LANDMARK_SPACING: ["Landmark spacing", "Minimum fine-cell distance between landmark footprints."],
    },
    // A selector's options, by value.
    options: {
      FINE: { 40: "Very Small", 60: "Small", 80: "Normal", 100: "Big", 120: "Very Big" },
      GAP_MIXED: { 3: "Very Dense", 4: "Dense", 5: "Normal", 6: "Sparse", 7: "Very Sparse" },
    },
    // Named for screen readers only: no heading is shown.
    groups: {
      spacing: "Avenue and Street spacing",
      shape: "Avenue and Street shape",
      buildings: "Building mix",
    },
    placeholders: {
      BANNED_BUILDINGS: "e.g. 001, 002",
    },
  },
};

// An error's code from Python, as the dialog's title and message, given its tab's text and its detail.
const ERRORS = {
  running: (tab) => ({ title: tab.running[0], message: tab.running[1] }),
  // ``detail`` is the knob's name.
  invalid_config: (tab, detail) => ({
    title: tab.invalidConfig,
    message: `"${TEXT.form.knobs[detail]?.[0] ?? detail}" isn't a valid setting.`,
  }),
  invalid_seed: () => ({ title: "Invalid seed", message: "Seed must be an integer." }),
  worlds_folder: (_tab, detail) => ({ title: "Could not open worlds folder", message: detail }),
  not_a_world: (_tab, detail) => ({
    title: "Not an MC world",
    message: `No region files (.mca) were found in:\n${detail}\n\nPlease select a valid MC world folder.`,
  }),
  no_world: () => ({
    title: "Missing world path",
    message: "Choose a valid MC world before selecting an area on the map.",
  }),
  areas_missing: () => ({
    title: "Invalid extraction region",
    message: "Choose an MC world and all three areas first.",
  }),
};

/** ``{code, detail}`` from Python, on tab ``tab``, as ``{title, message}`` for the error dialog. */
function describeError({ code, detail }, tab) {
  const describe = ERRORS[code];
  return describe ? describe(TEXT.tabs[tab], detail) : { title: "Something went wrong", message: detail || code };
}

/** A run's failure, as ``{title, message}``: the tab's own title, and the error's text if it had any. */
function describeFailure(tab, detail) {
  const title = TEXT.tabs[tab].failed;
  return { title, message: detail || title };
}
