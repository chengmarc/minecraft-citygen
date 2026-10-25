// Each tab's run bar: a hand-tuned weight per step its run reports, where each report puts the bar, and the bar's
// segments.
// Everything is keyed by tab (``extract``, ``preview``, ``build``), then by the step codes each tab's run reports (see
// ``run`` in citygen.step1_extract, citygen.step2_preview and citygen.step3_build), which Python passes on as they
// come: ``{step, completed, total, detail}``. The bar runs from 0 to 100. A report becomes where the bar jumps, where
// it creeps toward until the next report, and the words that stand in for the running segment's name (or null).

"use strict";

// Construction reports each of its eight steps (citygen.step3_build.CONSTRUCT_STEPS) by index as it starts it;
// text.js words each one (TEXT.stepDetails.build.construct).
const CONSTRUCT_WEIGHTS = [1, 1, 1, 1, 22, 4, 4, 16];

// Between reports the bar creeps toward the next milestone: up to ``headroom`` of the way there, moving every ``tickMs``
// by this share of what's left.
const CREEP_RATE = 0.10;

const RUN_STEPS = {
  extract: {
    weights: { scan_roads: 1, road_pieces: 5, road_sheet: 3, scan_builds: 8, build_pieces: 50, build_sheet: 33 },
    headroom: 0.90,
    tickMs: 120,
  },
  preview: {
    weights: { road_pieces: 8, build_pieces: 8, road_layout: 15, city_layout: 69 },
    headroom: 0.95,
    tickMs: 60,
  },
  build: {
    weights: {
      ...Object.fromEntries(CONSTRUCT_WEIGHTS.map((weight, n) => [`construct.${n}`, weight])), render: 5, world: 45,
    },
    // Construction's eight steps grouped: road network and grid; catalog and placements; assembly, voxels and trees;
    // the schematic. Then the render and the world export.
    segments: [["roads", 2], ["placement", 2], ["buildings", 3], ["schematic", 1], ["render", 1], ["world", 1]],
    headroom: 0.90,
    tickMs: 120,
  },
};

/** Where step ``index`` of ``weights`` starts, in percent of the run. */
function stepStart(weights, index) {
  const total = weights.reduce((sum, weight) => sum + weight, 0) || 1;
  return (weights.slice(0, index).reduce((sum, weight) => sum + weight, 0) / total) * 100;
}

/** Tab ``tab``'s run-bar segments, in step order: ``{code, start, end}`` in percent of the run (text.js names each
 *  code). A tab without ``segments`` has one per step. */
function runSegments(tab) {
  const { weights, segments } = RUN_STEPS[tab];
  const values = Object.values(weights);
  let index = 0;
  return (segments ?? Object.keys(weights).map((code) => [code, 1])).map(([code, count]) => {
    const span = { code, start: stepStart(values, index), end: stepStart(values, index + count) };
    index += count;
    return span;
  });
}

/** ``{value, softTarget}`` for ``completed`` of ``total`` through step ``index``; at its end, no soft target. */
function stepPosition(run, index, completed, total) {
  const weights = Object.values(run.weights);
  const start = stepStart(weights, index);
  const end = stepStart(weights, index + 1);
  total = total > 0 ? total : 1;
  completed = Math.min(Math.max(completed, 0), total);
  const value = start + (completed / total) * (end - start);
  if (completed >= total) return { value, softTarget: null };
  const next = start + ((completed + 1) / total) * (end - start);
  return { value, softTarget: value + (next - value) * run.headroom };
}

/** A run's report on tab ``tab``, as the bar's milestone: ``{value, softTarget, tickMs, creepRate, detail}``.
 *  Construction reports ``completed`` as the index of the step it's starting, out of eight. */
function runReport(tab, { step, completed, total }) {
  const run = RUN_STEPS[tab];
  const steps = Object.keys(run.weights);
  const creep = { tickMs: run.tickMs, creepRate: CREEP_RATE };
  if (step === "construct") {
    const done = completed >= CONSTRUCT_WEIGHTS.length;
    const index = steps.indexOf(`construct.${Math.min(completed, CONSTRUCT_WEIGHTS.length - 1)}`);
    return { ...stepPosition(run, index, done ? 1 : 0, 1), ...creep, detail: done ? null : TEXT.stepDetails.build.construct[completed] };
  }
  const shown = tab === "preview" ? TEXT.stepDetails.preview[step] : null;
  return { ...stepPosition(run, steps.indexOf(step), completed, total), ...creep, detail: shown };
}
