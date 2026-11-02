"""Turn a DEXIS tooth code into a Universal-numbering label.

DEXIS stores an image's teeth as an int built from FDI tooth numbers: 0 for
none, one FDI tooth (36), or two FDI corner teeth (1846 = 18 and 46). The
screen shows them in Universal numbering, and Dexis.ini's series use the same
corner-pair idea in Universal (1-30 is the right molar BW).
"""


def fdi_to_universal(fdi: int) -> str:
    q, t = divmod(fdi, 10)
    if not 1 <= t <= 8 or q not in range(1, 9):
        raise ValueError(f"not an FDI tooth: {fdi}")
    if q == 1:
        return str(9 - t)
    if q == 2:
        return str(8 + t)
    if q == 3:
        return str(25 - t)
    if q == 4:
        return str(24 + t)
    if t > 5:
        raise ValueError(f"not a primary FDI tooth: {fdi}")
    if q == 5:
        return chr(ord("A") + 5 - t)
    if q == 6:
        return chr(ord("F") + t - 1)
    if q == 7:
        return chr(ord("K") + 5 - t)
    return chr(ord("P") + t - 1)


# Each arch in FDI numbers, patient's right to left; the two rows of a dentition line up
# tooth over tooth, so the same position in the opposite row is the opposing tooth.
_ARCHES = {
    "permanent": (
        [*range(18, 10, -1), *range(21, 29)],
        [*range(48, 40, -1), *range(31, 39)],
    ),
    "primary": (
        [*range(55, 50, -1), *range(61, 66)],
        [*range(85, 80, -1), *range(71, 76)],
    ),
}


def teeth_fdi(code: int) -> list[int]:
    """Every FDI tooth a DEXIS tooth code covers, patient's right to left, upper first.

    One tooth is itself. A same-arch pair is the run between the corners. A cross-arch
    pair (a bitewing) is the upper run from its corner to the tooth over the lower corner,
    and the lower run from its corner to the tooth under the upper corner, the same span
    ``teeth_label`` prints. A code that mixes dentitions or does not decode returns its
    valid corners only, and [] when there are none.
    """
    if code <= 0:
        return []
    corners = [code] if code < 100 else [code // 100, code % 100]
    valid = [t for t in corners if _is_fdi(t)]
    if len(valid) < 2:
        return valid
    a, b = valid
    for upper, lower in _ARCHES.values():
        if a in upper + lower and b in upper + lower:
            break
    else:
        return valid  # one permanent, one primary
    if (a in upper) == (b in upper):
        row = upper if a in upper else lower
        i, j = sorted((row.index(a), row.index(b)))
        return row[i : j + 1]
    up, low = (a, b) if a in upper else (b, a)
    lo, hi = sorted((upper.index(up), lower.index(low)))
    return upper[lo : hi + 1] + lower[lo : hi + 1]


def _is_fdi(t: int) -> bool:
    try:
        fdi_to_universal(t)
    except ValueError:
        return False
    return True


def _upper(u: str) -> bool:
    return u.isdigit() and 1 <= int(u) <= 16 or u.isalpha() and u <= "J"


def teeth_label(code: int) -> tuple[str, str]:
    """Return (kind, teeth) for a DEXIS tooth code: kind is BW, PA, or ''.

    Same-arch pairs are a range (PA 20-21). A cross-arch pair is a bitewing,
    covering the upper corner to the tooth opposite the lower corner and back
    (1/30 -> BW 1-3 30-32). Codes that do not decode come back as ('', '').
    """
    if code <= 0:
        return "", ""
    try:
        if code < 100:
            return "PA", fdi_to_universal(code)
        a, b = fdi_to_universal(code // 100), fdi_to_universal(code % 100)
    except ValueError:
        return "", ""
    if not (a.isdigit() and b.isdigit()):
        return "PA", f"{a}-{b}"
    lo, hi = sorted((int(a), int(b)))
    if _upper(a) == _upper(b):
        return "PA", f"{lo}-{hi}" if lo != hi else str(lo)
    up, low = (int(a), int(b)) if _upper(a) else (int(b), int(a))
    up_end, low_end = 33 - low, 33 - up
    if up_end < up or low_end < low:
        return "BW", f"{up} {low}"
    return "BW", f"{up}-{up_end} {low}-{low_end}"
