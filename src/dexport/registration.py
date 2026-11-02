"""The DEXIS registration pair this install uses, supplied by the user.

``xfile.dll`` decodes nothing until ``XfileInit`` is given a name and code it accepts.
This package ships no pair. Each user supplies their own, from their own licensed DEXIS
install, in one of two places (first found wins):

1. the environment variable ``DEXIS_REGISTRATION`` as ``NAME:CODE``
2. the file ``%APPDATA%\\dexport\\registration.txt`` holding ``NAME:CODE`` on one line
   (``DEXIS_REGISTRATION_FILE`` names a different file)
"""

from __future__ import annotations

import os
from pathlib import Path

ENV = "DEXIS_REGISTRATION"
ENV_FILE = "DEXIS_REGISTRATION_FILE"

HELP = (
    "No DEXIS registration pair is configured. xfile.dll needs the name and code your "
    f"licensed DEXIS install uses. Set {ENV}=NAME:CODE, or put NAME:CODE on one line in "
    f"{{file}}. See REGISTRATION.md."
)


class RegistrationMissing(RuntimeError):
    pass


def default_file() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "dexport" / "registration.txt"


def config_file() -> Path:
    return Path(os.environ[ENV_FILE]) if os.environ.get(ENV_FILE) else default_file()


def parse(text: str) -> tuple[str, str]:
    line = next(
        (
            x.strip()
            for x in text.splitlines()
            if x.strip() and not x.lstrip().startswith("#")
        ),
        "",
    )
    name, sep, code = line.partition(":")
    if not sep or not name.strip() or not code.strip():
        raise RegistrationMissing("registration must be NAME:CODE on one line")
    return name.strip(), code.strip()


def load() -> tuple[str, str]:
    """The configured (name, code), or RegistrationMissing explaining where to put it."""
    if os.environ.get(ENV):
        return parse(os.environ[ENV])
    f = config_file()
    if f.is_file():
        return parse(read_text(f))
    raise RegistrationMissing(HELP.format(file=f))


def read_text(f: Path) -> str:
    """The file's text whatever Windows wrote it as: UTF-8 with or without a BOM (Notepad,
    ``Set-Content -Encoding UTF8``) or UTF-16 (PowerShell 5.1's ``>`` and ``Out-File``).
    A stray BOM left in the name would make DEXIS reject the pair without saying so."""
    try:
        raw = f.read_bytes()
    except OSError as e:
        raise RegistrationMissing(f"cannot read {f}: {e.strerror}") from e
    try:
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return raw.decode("utf-16")
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise RegistrationMissing(
            f"{f} is not readable text; save it as plain text holding NAME:CODE"
        ) from e


def configured() -> bool:
    try:
        load()
        return True
    except RegistrationMissing:
        return False
