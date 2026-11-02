"""Which patient DEXIS has open right now, read from files instead of DEXSRV32.DLL.

DEXIS keeps a few bookkeeping files at the top of the data root (``<root>\\``, not inside a
patient folder). The one that matters is ``<HOSTNAME>.pat``: the patient ID open on that
workstation, zero-padded, CRLF-terminated. DEXIS rewrites it as the operator moves between
patients, so reading it is the file-based equivalent of ``DXL_GetCurrentPatient`` and needs
no DLL, no open database, and no registration pair.

``DEXnet.lck`` names the host currently holding the DEXIS network lock. ``xpat.log`` is an
append log of opened patient folders; it is not a current-patient signal (its last line is
only the most recent *write*). ``DEXIS.CHK`` is a zero-byte flag.

This reads, never writes. The ID it returns is DEXIS's patient ID, the same number
:class:`~dexport.catalog.DexisRoot` folders by.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path

NET_LOCK = "DEXnet.lck"


def hostname() -> str:
    """This workstation's name, as DEXIS spells the ``<host>.pat`` file (upper case)."""
    return socket.gethostname().upper()


def pat_file(root: Path | str, host: str | None = None) -> Path:
    """Path of the ``<host>.pat`` file for ``host`` (this workstation if omitted)."""
    return Path(root) / f"{host or hostname()}.pat"


def _read_id(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="latin-1").strip()
    except OSError:
        return None
    try:
        return int(text)  # zero-padded, e.g. "12345"
    except ValueError:
        return None


def current_patient(root: Path | str, host: str | None = None) -> int | None:
    """The patient ID DEXIS has open on ``host`` (this workstation if omitted).

    None when nothing is open, the file is absent or unreadable, or its contents are not an
    ID. Pass another workstation's name to see what is open there.
    """
    return _read_id(pat_file(root, host))


@dataclass(frozen=True)
class OpenPatient:
    host: str
    patient_id: int


def open_patients(root: Path | str) -> list[OpenPatient]:
    """Every workstation with a patient open, from the ``<host>.pat`` files at the root top.

    Sorted by host. A ``.pat`` that is empty or not an ID is skipped.
    """
    out: list[OpenPatient] = []
    for f in sorted(Path(root).glob("*.pat")):
        pid = _read_id(f)
        if pid is not None:
            out.append(OpenPatient(f.stem.upper(), pid))
    return out


def net_lock_holder(root: Path | str) -> str | None:
    """The host named in ``DEXnet.lck``, or None if the lock file is absent or empty."""
    try:
        text = (Path(root) / NET_LOCK).read_text(encoding="latin-1").strip()
    except OSError:
        return None
    return text or None
