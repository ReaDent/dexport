"""Where a patient's images live in a DEXIS data root, and which files are live.

A patient folder is the patient ID zero-padded to five digits and split one digit per
level (12345 -> root/1/2/3/4/5). Two index files inside name the live images: DEXIS.dat
(the x-ray side) and DEVIS.dat (the photo side). The indexes are the source of truth: a
.DEX on disk that no index lists is not a live image. The side an image sits on is NOT
its kind (phone photos turn up on the x-ray side and outside x-rays on the photo side);
``ImageMeta.kind`` from the bit depth decides that.

The data root is ``DEXIS_DATA_ROOT`` if set, else the ``xdata`` path in DEXIS's own
``Dexis.ini`` (``C:\\DEXIS\\Dexis.ini``).
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

DEXIS_INI = Path(r"C:\DEXIS\Dexis.ini")
SETTLE_SECONDS = 120  # a file modified this recently may still be being written


def default_root(ini: Path = DEXIS_INI) -> Path | None:
    """``DEXIS_DATA_ROOT``, else ``xdata=`` from Dexis.ini, else None."""
    if os.environ.get("DEXIS_DATA_ROOT"):
        return Path(os.environ["DEXIS_DATA_ROOT"])
    try:
        text = ini.read_text(encoding="latin-1")
    except OSError:
        return None
    m = re.search(r"^\s*xdata\s*=\s*(.+?)\s*$", text, re.M | re.I)
    return Path(m.group(1).strip('"')) if m else None


@dataclass(frozen=True)
class DexFile:
    path: Path
    source: (
        str  # 'xray' (DEXIS.dat) or 'photo' (DEVIS.dat): the index side, not the kind
    )
    size: int
    mtime: float

    @property
    def settling(self) -> bool:
        return time.time() - self.mtime < SETTLE_SECONDS


class DexisRoot:
    def __init__(self, root: Path | str | None = None):
        if root is None:
            root = default_root()
        if root is None:
            raise FileNotFoundError(
                "no DEXIS data root: pass --dexis-root, set DEXIS_DATA_ROOT, or check "
                f"xdata= in {DEXIS_INI}"
            )
        self.root = Path(root)

    def patient_folder(self, patient_id: int) -> Path:
        return self.root.joinpath(*str(patient_id).zfill(5))

    def images(self, patient_id: int) -> list[DexFile]:
        """Every image the patient's indexes list that exists on disk, index order."""
        folder = self.patient_folder(patient_id)
        if not folder.is_dir():
            raise FileNotFoundError(f"no DEXIS folder for patient {patient_id}")
        return list_indexed(self.root, folder)


def list_indexed(root: Path, folder: Path) -> list[DexFile]:
    out: list[DexFile] = []
    seen: set[Path] = set()
    for source, index in (("xray", "DEXIS.dat"), ("photo", "DEVIS.dat")):
        f = folder / index
        if not f.exists():
            continue
        for line in f.read_text(encoding="latin-1").splitlines():
            parts = line.split()
            if parts and parts[-1].upper().endswith(".DEX"):
                p = root / parts[-1]
                if p in seen:
                    continue  # listed twice, or on both sides
                seen.add(p)
                if p.exists():
                    st = p.stat()
                    out.append(DexFile(p, source, st.st_size, st.st_mtime))
    return out
