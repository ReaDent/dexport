"""Decode a .DEX and write it out: as a picture the way DEXIS shows it (jpg, png, tif, with
a metadata sidecar), or as DICOM the way DEXIS's own DICOM export writes it (dcm)."""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import dicom
from .clearvu import ClearVu
from .xfile import ImageMeta, Xfile, upright

FORMATS = {"jpg": ("JPEG", {"quality": 92}), "png": ("PNG", {}), "tif": ("TIFF", {})}
ALL_FORMATS = [*FORMATS, "dcm"]


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
    """Holds one Xfile and one ClearVu so a batch pays the DLL load once.

    ``anonymize`` applies to DICOM output: no patient name, ID or birthdate, and UIDs
    salted per Exporter so they cannot be traced back to the patient.
    """

    def __init__(
        self,
        dexis_dir: Path | str | None = None,
        display: bool = True,
        anonymize: bool = False,
    ):
        kw = {"dexis_dir": dexis_dir} if dexis_dir else {}
        self.xf = Xfile(**kw)
        self.cv = ClearVu(**kw) if display else None
        self.anonymize = anonymize
        self.uids = dicom.UidMaker.anonymous() if anonymize else dicom.UidMaker()

    def render(self, path: Path | str) -> tuple[Image.Image, ImageMeta, int]:
        """Decoded, processed, upright image plus its meta and the decode time in ms."""
        meta = self.xf.meta(path)
        t0 = time.perf_counter()
        im = self.xf.read(path)
        ms = round((time.perf_counter() - t0) * 1000)
        im = self.cv.display(im, meta) if self.cv else upright(im, meta.rotation)
        return im, meta, ms

    def export(
        self,
        path: Path | str,
        dest: Path,
        fmt: str = "jpg",
        sidecar: bool = True,
        patient_id: int | None = None,
    ) -> ExportResult:
        """Write one image. ``patient_id`` (the DEXIS ID) is used only by DICOM output."""
        if fmt == "dcm":
            return self.export_dicom(path, dest, patient_id)
        pil_fmt, kw = FORMATS[fmt]
        im, meta, ms = self.render(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, pil_fmt, **kw)
        if sidecar:
            dest.with_suffix(dest.suffix + ".json").write_text(
                json.dumps(meta.as_dict(), indent=1)
            )
        return ExportResult(Path(path), dest, meta, im.mode, im.width, im.height, ms)

    def export_dicom(
        self, path: Path | str, dest: Path, patient_id: int | None = None
    ) -> ExportResult:
        path = Path(path)
        meta = self.xf.meta(path)
        t0 = time.perf_counter()
        raw = self.xf.read(path)
        ms = round((time.perf_counter() - t0) * 1000)
        im = dicom.pixels(raw, meta)
        real = dicom.read_identity(path, patient_id)
        # The UIDs keep patients apart even when the identity is left out (salted then).
        key = real.patient_id or real.name + real.birth_date or str(path.parent)
        identity = dicom.Identity() if self.anonymize else real
        ds = dicom.dataset(
            im,
            meta,
            identity,
            self.uids,
            model=dicom.device_model(path),
            # DICOM dates and times are local wall-clock, like DEXIS's own
            file_date=dt.datetime.fromtimestamp(path.stat().st_mtime),  # noqa: DTZ006
            patient_key=key,
        )
        dicom.write(ds, dest)
        return ExportResult(path, dest, meta, im.mode, im.width, im.height, ms)
