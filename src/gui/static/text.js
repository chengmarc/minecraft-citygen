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
  mapMissing: (path) => `World preview not found:\n${path}`,
  mapFailed: "Failed to load world preview.",
  mapLoading: "Loading world preview...",
  mapDrawing: "Drawing your world from above. You can already pan, zoom, and choose your area.",
};

// An error's code from Python, as the dialog's title and message, given its tab's text and its detail.
const ERRORS = {
  running: (tab) => ({ title: tab.running[0], message: tab.running[1] }),
  invalid_config: (tab, detail) => ({ title: tab.invalidConfig, message: detail }),
  invalid_seed: (_tab, detail) => ({ title: "Invalid seed", message: detail }),
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
