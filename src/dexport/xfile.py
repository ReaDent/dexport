"""ctypes binding for DEXIS's xfile.dll: decode .DEX files and read their metadata.

Every export is ``__stdcall`` with ANSI C strings. Signatures were recovered from the
disassembly and confirmed by running them; see ``docs/api.md``. Only read
exports are bound here. ``tests/test_no_writes.py`` pins that.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import struct
import tempfile
from ctypes import POINTER, c_char_p, c_int, c_void_p, create_string_buffer
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from . import require_arch
from .registration import load as load_registration
from .tonecurve import is_identity

DEFAULT_DEXIS_DIR = Path(r"C:\DEXIS")

# OriLux rotation code -> Pillow transpose that puts the image the way DEXIS shows it.
# 0 and 1 are "no turn"; mapped from a full FMX on 2026-10-06.
ROTATE = {
    2: Image.Transpose.ROTATE_270,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.ROTATE_90,
}

TYPE_NAMES = {
    5: "intraoral x-ray",
    6: "x-ray (other system)",
    9: "IOC Snapshot photo",
    10: "imported image or video frame",
}


@dataclass
class ImageMeta:
    """What xfile.dll reports about a .DEX without decoding it."""

    path: Path
    header_width: int | None = None  # over-reports by 4 to 7 px on a third of files
    header_height: int | None = None
    bps: int | None = None  # 8 = x-ray, 24 = photo; reliable
    type: int | None = None
    teeth: int = 0
    acq_date: str = ""  # YYYYMMDD
    acq_time: str = ""  # HHMM, HHMMSS, or empty
    rotation: int | None = None
    lux: tuple[int, ...] = field(default_factory=tuple)  # OriLux values 2..7
    frames: int = 1
    pixel_spacing: tuple[int, int] | None = None

    @property
    def kind(self) -> str:
        """'xray' or 'photo' from the stored bit depth, 'unknown' if unreadable."""
        if self.bps == 8:
            return "xray"
        if self.bps == 24:
            return "photo"
        return "unknown"

    @property
    def captured(self) -> dt.datetime | None:
        if len(self.acq_date) != 8:
            return None
        t = (self.acq_time + "000000")[:6] if self.acq_time else "000000"
        try:
            return dt.datetime.strptime(self.acq_date + t, "%Y%m%d%H%M%S")
        except ValueError:
            return None

    @property
    def edited(self) -> bool:
        """A saved brightness/contrast edit: any OriLux window DEXIS draws a curve for."""
        return len(self.lux) >= 4 and not is_identity(*self.lux[:4])

    def as_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "path"}
        d["path"] = str(self.path)
        d["kind"] = self.kind
        d["captured"] = self.captured.isoformat() if self.captured else None
        d["edited"] = self.edited
        d["type_name"] = TYPE_NAMES.get(self.type or -1)
        return d


class Xfile:
    """One loaded xfile.dll. Construct once, reuse for every file."""

    def __init__(
        self,
        dexis_dir: Path | str = DEFAULT_DEXIS_DIR,
        registration: tuple[str, str] | None = None,
    ):
        require_arch()
        name, code = registration or load_registration()
        self.dexis_dir = Path(dexis_dir)
        x = self.x = ctypes.WinDLL(str(self.dexis_dir / "xfile.dll"))
        x.XfileInit.argtypes = [c_char_p, c_char_p, c_char_p]
        x.XfileReadImg.argtypes = [c_char_p]
        x.XfileReadImg.restype = c_void_p
        x.XfileReadImgFrame.argtypes = [c_char_p, c_int]
        x.XfileReadImgFrame.restype = c_void_p
        x.XfileFreeImg.argtypes = [c_void_p]
        x.XfileReadNumberOfFrames.argtypes = [c_char_p]
        x.XfileTryReadImageSize.argtypes = [c_char_p] + [POINTER(c_int)] * 3
        x.XfileTryReadTypeAndTeeth.argtypes = [c_char_p] + [POINTER(c_int)] * 2
        x.XfileTryReadAcquisitionDateTime.argtypes = [c_char_p, c_char_p, c_char_p]
        x.XfileTryReadOriLux.argtypes = [c_char_p] + [POINTER(c_int)] * 7
        x.XfileTryReadPixelSpacing.argtypes = [c_char_p, POINTER(c_int), POINTER(c_int)]
        x.XfileReadThumbnail.argtypes = [c_char_p, c_int, POINTER(c_int)]
        x.XfileReadThumbnail.restype = c_void_p
        x.XfileCheckCrc.argtypes = [c_char_p]
        x.XfileTryReadBlackWhite.argtypes = [c_char_p, POINTER(c_int), POINTER(c_int)]
        # XfileInit's first argument is a folder it probes for a logging DLL. A temp dir keeps
        # it from writing anything next to the real install.
        log_dir = Path(tempfile.gettempdir()) / "dexport-xfile"
        log_dir.mkdir(exist_ok=True)
        # A wrong pair still returns 1 here; every read then fails (see REGISTRATION.md).
        self.init_rc = x.XfileInit(_ansi(log_dir), name.encode(), code.encode())

    # -- metadata -------------------------------------------------------------------------

    def meta(self, path: Path | str) -> ImageMeta:
        path = Path(path)
        p = _encode(path)
        m = ImageMeta(path=path)
        w, h, bps = c_int(), c_int(), c_int()
        if self.x.XfileTryReadImageSize(p, w, h, bps):
            m.header_width, m.header_height, m.bps = w.value, h.value, bps.value
        ty, teeth = c_int(), c_int()
        if self.x.XfileTryReadTypeAndTeeth(p, ty, teeth):
            m.type, m.teeth = ty.value, teeth.value
        d, t = create_string_buffer(64), create_string_buffer(64)
        if self.x.XfileTryReadAcquisitionDateTime(p, d, t):
            m.acq_date = d.value.decode(errors="replace")
            m.acq_time = t.value.decode(errors="replace")
        o = [c_int() for _ in range(7)]
        if self.x.XfileTryReadOriLux(p, *o):
            m.rotation = o[0].value
            m.lux = tuple(v.value for v in o[1:])
        # Two ints (the DLL logs them as "pixw/h=%d %d"); unit not yet confirmed, so they
        # are passed through as reported.
        sx, sy = c_int(), c_int()
        if self.x.XfileTryReadPixelSpacing(p, sx, sy) and sx.value > 0:
            m.pixel_spacing = (sx.value, sy.value)
        m.frames = self.x.XfileReadNumberOfFrames(p) or 1
        return m

    def check_crc(self, path: Path | str) -> int:
        """0 = intact, 1 = CRC mismatch, -1 = unreadable. The CRC covers only part of the
        file: a flipped byte near the start is caught, one deep in the pixel data is not."""
        return self.x.XfileCheckCrc(_encode(path))

    def black_white(self, path: Path | str) -> tuple[int, int] | None:
        """The two ints of the file's '{black white}' tag, or None when it has none.

        Values unverified: none of the vendor samples carries the tag."""
        b, w = c_int(), c_int()
        if self.x.XfileTryReadBlackWhite(_encode(path), b, w):
            return b.value, w.value
        return None

    # -- pixels ---------------------------------------------------------------------------

    def _to_pil(self, img: int) -> Image.Image:
        header = ctypes.string_at(img, 24)
        _w, h, _bpp, _, stride, data = struct.unpack("<5iI", header)
        try:
            buf = ctypes.string_at(data, stride * h)
        finally:
            self.x.XfileFreeImg(img)
        return struct_to_image(header, buf)

    def read(self, path: Path | str) -> Image.Image:
        """Decode to a Pillow image: 'L' for x-rays, 'RGB' for photos. Raw, not rotated."""
        img = self.x.XfileReadImg(_encode(path))
        if not img:
            raise DecodeError(f"XfileReadImg returned NULL for {Path(path).name}")
        return self._to_pil(img)

    def thumbnail(self, path: Path | str, max_size: int) -> tuple[Image.Image, int]:
        """Fast reduced decode. Returns the image and its divisor (1, 2, or 4): the largest
        divisor that keeps the long side at or above ``max_size``, so the result is never
        smaller than asked unless the original is."""
        scale = c_int()
        img = self.x.XfileReadThumbnail(_encode(path), max_size, scale)
        if not img:
            raise DecodeError(f"XfileReadThumbnail returned NULL for {Path(path).name}")
        return self._to_pil(img), scale.value

    def read_frame(self, path: Path | str, n: int) -> Image.Image:
        img = self.x.XfileReadImgFrame(_encode(path), n)
        if not img:
            raise DecodeError(
                f"XfileReadImgFrame({n}) returned NULL for {Path(path).name}"
            )
        return self._to_pil(img)


def struct_to_image(header: bytes, pixels: bytes) -> Image.Image:
    """Pillow image from xfile's 24-byte image struct and its pixel buffer.

    struct { int32 width, height, bitsPerPixel, unused, stride; uint8 *pixels; }
    Rows are top-down and stride-padded; 24-bit is BGR, 8-bit one byte per pixel.
    """
    w, h, bpp, _, stride, _ptr = struct.unpack("<5iI", header)
    if bpp == 24:
        return Image.frombuffer("RGB", (w, h), pixels, "raw", "BGR", stride, 1)
    if bpp == 8:
        return Image.frombuffer("L", (w, h), pixels, "raw", "L", stride, 1)
    raise ValueError(f"unexpected bits per pixel {bpp}")


class DecodeError(RuntimeError):
    pass


def _encode(path: Path | str) -> bytes:
    """Path bytes for the DLL, after proving the file exists: xfile.dll faults (access
    violation) on a missing path instead of returning NULL."""
    path = Path(path)
    if not path.is_file():
        raise DecodeError(f"no such file: {path}")
    return _ansi(path)


def _ansi(path: Path | str) -> bytes:
    return str(path).encode("mbcs")  # the exports take ANSI strings


def upright(im: Image.Image, rotation: int | None) -> Image.Image:
    """Turn a decoded image the way DEXIS displays it."""
    return im.transpose(ROTATE[rotation]) if rotation in ROTATE else im
