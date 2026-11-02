"""Decode a .DEX and write it out the way DEXIS would show it, with a metadata sidecar."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .clearvu import ClearVu
from .xfile import ImageMeta, Xfile, upright

FORMATS = {"jpg": ("JPEG", {"quality": 92}), "png": ("PNG", {}), "tif": ("TIFF", {})}


@dataclass
class ExportResult:
    source: Path
    dest: Path
    meta: ImageMeta
    mode: str
    width: int
    height: int
    decode_ms: int


class Exporter:
    """Holds one Xfile and one ClearVu so a batch pays the DLL load once."""

    def __init__(self, dexis_dir: Path | str | None = None, display: bool = True):
        kw = {"dexis_dir": dexis_dir} if dexis_dir else {}
        self.xf = Xfile(**kw)
        self.cv = ClearVu(**kw) if display else None

    def render(self, path: Path | str) -> tuple[Image.Image, ImageMeta, int]:
        """Decoded, processed, upright image plus its meta and the decode time in ms."""
        meta = self.xf.meta(path)
        t0 = time.perf_counter()
        im = self.xf.read(path)
        ms = round((time.perf_counter() - t0) * 1000)
        im = self.cv.display(im, meta) if self.cv else upright(im, meta.rotation)
        return im, meta, ms

    def export(
        self, path: Path | str, dest: Path, fmt: str = "jpg", sidecar: bool = True
    ) -> ExportResult:
        pil_fmt, kw = FORMATS[fmt]
        im, meta, ms = self.render(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, pil_fmt, **kw)
        if sidecar:
            dest.with_suffix(dest.suffix + ".json").write_text(
                json.dumps(meta.as_dict(), indent=1)
            )
        return ExportResult(Path(path), dest, meta, im.mode, im.width, im.height, ms)
