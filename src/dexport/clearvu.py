"""DEXIS's on-screen x-ray processing, reproduced through its own ClearVuFilter.dll.

DEXIS.EXE in ``clearvumode=2`` runs: raw decode -> ClearVuFilter.dll guided filter ->
3x3 median (skipped when a side is 2000 px or more) -> rotate -> JPEG. With that chain
16 of 20 exports reproduced bit-exact (docs/display.md). The other
4 carry a saved brightness/contrast edit; ``window_lut`` applies DEXIS's own edit curve,
recovered bit-exact from dexxdb.dll in 2026-11 (``tonecurve``). Photos skip the filter and
go through DEXIS's own color rendering with the saved edit (``tonecurve.photo_edit``).
"""

from __future__ import annotations

import ctypes
import os
import struct
from ctypes import c_void_p
from pathlib import Path

from PIL import Image, ImageFilter

from . import require_arch
from .tonecurve import edit_curve, is_identity, photo_edit
from .xfile import DEFAULT_DEXIS_DIR, ImageMeta, upright


class ClearVu:
    """One loaded ClearVuFilter.dll with the settings block DEXIS.EXE uses."""

    BLOCK = 0xD64
    PRESET_FLAGS = (0x590, 0x5D4, 0x618, 0x65C, 0x6A0, 0x6E4)

    def __init__(
        self, dexis_dir: Path | str = DEFAULT_DEXIS_DIR, size=15, strength=200, eps=100
    ):
        require_arch()
        dexis_dir = Path(dexis_dir)
        os.add_dll_directory(str(dexis_dir))  # the opencv_*453.dll files live beside it
        f = self.f = ctypes.WinDLL(str(dexis_dir / "ClearVuFilter.dll"))
        f.BetaFilterInit.argtypes = [c_void_p]
        f.BetaFilter.argtypes = [c_void_p, c_void_p]
        blk = self.blk = ctypes.create_string_buffer(self.BLOCK)
        blk[0:16] = b"DEXIS9 Software\0"
        f.BetaFilterInit(blk)
        for off in self.PRESET_FLAGS:
            struct.pack_into(
                "<i", blk, off, -1
            )  # no built-in preset; the numbers below rule
        struct.pack_into("<5i", blk, 0xB2C, 2, 0, 0, 0xFF, 0xFF)
        struct.pack_into("<i", blk, 0xD50, 0)
        struct.pack_into("<3i", blk, 0xD58, size, strength, eps)

    def filter(self, im: Image.Image) -> Image.Image:
        """Guided filter plus DEXIS's median pass on an 8-bit image; others pass through."""
        if im.mode != "L":
            return im
        w, h = im.size
        pix = ctypes.create_string_buffer(im.tobytes(), w * h)
        hdr = ctypes.create_string_buffer(
            struct.pack("<5iI", w, h, 8, 0, w, ctypes.addressof(pix)), 24
        )
        self.f.BetaFilter(self.blk, hdr)
        out = Image.frombuffer("L", (w, h), pix.raw[: w * h], "raw", "L", w, 1)
        return out if max(w, h) >= 2000 else out.filter(ImageFilter.MedianFilter(3))

    def display(
        self, im: Image.Image, meta: ImageMeta, apply_edit: bool = True
    ) -> Image.Image:
        """The full chain: filter, saved edit, then the display rotation.

        X-rays get the edit curve on the gray levels; photos go through DEXIS's luma
        rendering (``tonecurve.photo_edit``), which DEXIS applies to every photo.
        """
        out = self.filter(im)
        if apply_edit and out.mode == "L" and meta.edited:
            lut = window_lut(*meta.lux[:4])
            if lut:
                out = out.point(lut)
        elif apply_edit and out.mode == "RGB" and len(meta.lux) >= 4:
            out = photo_edit(out, edit_curve(*meta.lux[:4]))
        return upright(out, meta.rotation)


def window_lut(a1: int, a2: int, b1: int, b2: int) -> list[int] | None:
    """DEXIS's tone curve for a saved brightness/contrast edit; None when there is no edit.

    a1, a2, b1, b2 are OriLux values 2 to 5. Bit-exact with DEXIS (see ``tonecurve``).
    """
    if is_identity(a1, a2, b1, b2):
        return None
    return edit_curve(a1, a2, b1, b2)
