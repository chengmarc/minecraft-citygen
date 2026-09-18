"""Helpers every pipeline step module uses; the base of the pipeline package.

Step modules import this, never :mod:`pipeline.stages`: the stage registry
loads the step modules, so they must not depend back on it.

- :func:`noop` is the default logger/progress callback, so a step body can call
  ``logger(...)``/``progress(...)`` unconditionally.
- :func:`run_stage_cli` turns a step's ``run`` into a command-line entry point,
  reading each option's default from ``run``'s own signature.
"""

from __future__ import annotations

import argparse
import inspect


def noop(*args, **kwargs) -> None:
    """A logger/progress callback that discards its arguments."""


# CLI option specs shared by step modules and the stage registry CLI.
# Keys match ``run`` keyword names; underscores map to hyphenated CLI flags.
CLI_OPTIONS = {
    "seed": {"type": int, "help": "generation seed"},
    "fine": {"type": int, "help": "fine grid edge in cells (even)"},
    "preview": {"type": int, "help": "edge of preview png (0 = full res)"},
    "out": {"type": str, "help": "output path (default: derived from seed)"},
    "key": {"type": str, "help": "render one catalog key, e.g. 001"},
    "no_ground_fill": {
        "action": "store_true",
        "help": "leave empty non-road lot cells as air instead of filling them",
    },
}


def add_options(parser, params, defaults):
    """Add a ``--flag`` per name in ``params``; ``defaults(name)`` gives its default."""
    for name in params:
        parser.add_argument(f"--{name.replace('_', '-')}", default=defaults(name), **CLI_OPTIONS[name])


def run_stage_cli(run, *params: str, logger=print):
    """Run a step module's ``run`` as a command-line script.

    ``params`` names the options to expose (keys of :data:`CLI_OPTIONS`);
    each option's default is taken from ``run``'s own signature.
    """
    signature = inspect.signature(run)
    parser = argparse.ArgumentParser()
    add_options(parser, params, lambda name: signature.parameters[name].default)
    return run(logger=logger, **vars(parser.parse_args()))
