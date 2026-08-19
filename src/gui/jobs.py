"""Background job helpers for GUI actions."""

from __future__ import annotations

import threading
from tkinter import messagebox


def run_weighted_tasks_async(
    owner,
    button,
    tasks,
    start_status,
    fail_title,
    fail_status,
    complete_status,
    on_success,
):
    def worker():
        owner.after(0, lambda: button.configure(state="disabled"))
        owner.after(0, owner._start_progress)
        owner.after(0, lambda: owner.set_status(start_status))

        try:
            completed_weight = 0
            total_tasks = len(tasks)
            for index, (label, weight, func) in enumerate(tasks, start=1):
                owner.after(
                    0,
                    lambda index=index, total=total_tasks, label=label, completed=completed_weight, weight=weight:
                        owner._begin_script_progress(
                            completed,
                            completed + weight,
                            f"Running {index}/{total}: {label}",
                        ),
                )
                func()
                completed_weight += weight
                owner.after(0, lambda value=completed_weight: owner._complete_script_progress(value))
        except Exception as exc:  # boundary: surface any task failure to the GUI
            message = str(exc).strip()
            owner.after(0, lambda: owner.set_status(fail_status))
            owner.after(0, lambda: messagebox.showerror(fail_title, message))
        else:
            owner.after(0, on_success)
            owner.after(0, owner._finish_progress)
            owner.after(0, lambda: owner.set_status(complete_status))
        finally:
            owner.after(0, owner._stop_progress)
            owner.after(0, lambda: button.configure(state="normal"))

    threading.Thread(target=worker, daemon=True).start()

