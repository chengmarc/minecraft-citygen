"""Override PyInstaller's tkinter exclusion for Python installs with valid files but broken auto-detection."""


def pre_find_module_path(hook_api):
    # Intentionally do nothing.
    #
    # PyInstaller's stock hook excludes tkinter entirely when it fails to
    # instantiate Tcl during analysis. This repo bootstraps Tcl/Tk paths at
    # runtime and ships the Tcl/Tk script directories explicitly, so the
    # exclusion is counterproductive here.
    return
