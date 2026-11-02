"""The package is read-only toward DEXIS: no write export may ever be bound.

XimgTryExport* is here too: its .tif and .dcm exports write a UID into the source .DEX."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "dexport"
WRITE = re.compile(
    r"\b(Xfile(Update|Write|Set|Make|Add)\w*|Xpat\w*(Add|Set)\w*|Xdb\w*(Set|Add|Delete)\w*|Ximg(Set|Delete|TryAdd|TryExport)\w*)\b"
)


def test_no_write_exports_named_in_source():
    hits = []
    for py in SRC.rglob("*.py"):
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if WRITE.search(line) and not line.lstrip().startswith(("#", '"""', "- ")):
                hits.append(f"{py.name}:{n}: {line.strip()}")
    assert not hits, "\n".join(hits)
