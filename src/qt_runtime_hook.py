"""Ensure a frozen Encounter Forge process uses its bundled Qt libraries.

Some developer tools set Qt environment variables or add another Qt release to
PATH.  A Qt extension can then bind to an incompatible Qt6Core DLL before
PySide6 starts, producing Windows' unhelpful "specified procedure could not be
found" error.  This hook runs before the application imports PySide6.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


if sys.platform == "win32" and getattr(sys, "frozen", False):
    bundle = Path(sys._MEIPASS)
    _dll_directory_handles = []
    # Do not inherit plugin locations belonging to an unrelated Qt install.
    for variable in ("QTDIR", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        os.environ.pop(variable, None)

    # Extension-module dependencies are resolved before the application code.
    # Put this bundle first and register its Qt directories with the modern
    # Windows loader used by Python 3.8+.
    directories = (bundle, bundle / "PySide6", bundle / "PySide6" / "Qt" / "bin")
    for directory in directories:
        if directory.is_dir():
            directory_text = str(directory)
            os.environ["PATH"] = directory_text + os.pathsep + os.environ.get("PATH", "")
            _dll_directory_handles.append(os.add_dll_directory(directory_text))
