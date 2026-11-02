"""Headless DEXIS 9 image access through DEXIS's own DLLs.

Every DEXIS DLL is 32-bit x86, so this package only works under a 32-bit Windows
Python (``uv run --python cpython-3.12-windows-x86``). Importing elsewhere raises
an ImportError naming the fix instead of failing later inside ctypes.
"""

import ctypes
import sys

__version__ = "0.1.0"

VERIFIED_DEXIS_VERSION = (
    "9.5.3"  # xfile.dll and ClearVuFilter.dll dated 16-May-2023 / 19-Apr-2023
)


def arch_ok() -> bool:
    return sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 4


def require_arch() -> None:
    if not arch_ok():
        raise ImportError(
            "dexport needs 32-bit Windows Python: "
            "uv run --python cpython-3.12-windows-x86 ..."
        )
