#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./pipeline.sh STEP [--seed N] [--fine N] [--preview N]

Steps:
  roads-sim
  roads-prod-extract
  roads-prod-render
  builds-sim
  builds-prod-extract
  builds-prod-render
  grid-sim
  grid-prod-construct
  grid-prod-render
  city-sim
  city-prod-construct
  city-prod-render
  all-sim
  all-prod
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

step="$1"
shift
seed=5
fine=120
preview=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed|-s)
      seed="$2"
      shift 2
      ;;
    --fine|-f)
      fine="$2"
      shift 2
      ;;
    --preview|-p)
      preview="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_python() {
  python "$@"
}

case "$step" in
  roads-sim)
    run_python "01_roads_simulation/draw_roads.py"
    ;;
  roads-prod-extract)
    run_python "01_roads_production/schematics/extract_roads.py"
    ;;
  roads-prod-render)
    run_python "01_roads_production/render_roads.py"
    ;;
  grid-sim)
    run_python "03_grid_simulation/draw_grid.py" --seed "$seed" --fine "$fine" --preview "$preview"
    ;;
  grid-prod-construct)
    run_python "03_grid_production/schematics/construct_grid.py" --seed "$seed" --fine "$fine"
    ;;
  grid-prod-render)
    run_python "03_grid_production/render_grid.py"
    ;;
  builds-sim)
    run_python "02_builds_simulation/draw_builds.py"
    ;;
  builds-prod-extract)
    run_python "02_builds_production/schematics/extract_builds.py"
    ;;
  builds-prod-render)
    run_python "02_builds_production/render_builds.py"
    ;;
  city-sim)
    run_python "04_city_simulation/draw_city.py" --seed "$seed" --fine "$fine" --preview "$preview"
    ;;
  city-prod-construct)
    run_python "04_city_production/schematics/construct_city.py" --seed "$seed" --fine "$fine"
    ;;
  city-prod-render)
    run_python "04_city_production/render_city.py"
    ;;
  all-sim)
    run_python "01_roads_simulation/draw_roads.py"
    run_python "02_builds_simulation/draw_builds.py"
    run_python "03_grid_simulation/draw_grid.py" --seed "$seed" --fine "$fine" --preview "$preview"
    run_python "04_city_simulation/draw_city.py" --seed "$seed" --fine "$fine" --preview "$preview"
    ;;
  all-prod)
    run_python "01_roads_production/schematics/extract_roads.py"
    run_python "01_roads_production/render_roads.py"
    run_python "02_builds_production/schematics/extract_builds.py"
    run_python "02_builds_production/render_builds.py"
    run_python "03_grid_production/schematics/construct_grid.py" --seed "$seed" --fine "$fine"
    run_python "03_grid_production/render_grid.py"
    run_python "04_city_production/schematics/construct_city.py" --seed "$seed" --fine "$fine"
    run_python "04_city_production/render_city.py"
    ;;
  *)
    echo "unknown step: $step" >&2
    usage >&2
    exit 2
    ;;
esac
