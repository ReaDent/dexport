"""Tests that need the DLLs run against the sample images every DEXIS 9 install ships in
``C:\\DEXIS\\Simulation`` (no patient data), with the registration pair the user has
configured (see REGISTRATION.md). Without them those tests skip; the pure-Python ones
always run."""

import os
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
DEXIS_DIR = Path(os.environ.get("DEXIS_DIR", r"C:\DEXIS"))
FIXTURES = Path(os.environ.get("DEXIS_SAMPLES", str(DEXIS_DIR / "Simulation")))


def dll_available() -> bool:
    try:
        from dexport import arch_ok
        from dexport.registration import configured

        return (
            arch_ok()
            and (DEXIS_DIR / "xfile.dll").exists()
            and (FIXTURES / "DCQ10.DEX").exists()
            and configured()
        )
    except ImportError:
        return False


needs_dll = pytest.mark.skipif(
    not dll_available(),
    reason="needs 32-bit Windows Python, an installed DEXIS with its Simulation samples, and a configured registration pair",
)


@pytest.fixture(scope="session")
def xfile():
    from dexport.xfile import Xfile

    return Xfile(DEXIS_DIR)


@pytest.fixture(scope="session")
def clearvu():
    from dexport.clearvu import ClearVu

    return ClearVu(DEXIS_DIR)
