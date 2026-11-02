"""DEXIS's saved-edit tone curve, bit-exact.

Transcribed from dexxdb.dll 9.5.3 (builder at 0x449b7c; helpers 0x449990, 0x4497c8,
0x449084, 0x4496b8, 0x449730) and checked against 233 palettes DEXIS wrote through
dexxdb's export call, including decreasing and crossed windows: every entry matches. The four
numbers are the OriLux window a1, a2, b1, b2 (also the DEXIS.dat window columns).

Shape: a quadratic Bezier from (0, 0) with control (a1, a2) to Q1, a straight line to Q2,
and a quadratic Bezier with control (b1, b2) to (255, 255), where Q1 and Q2 are the
quarter points of (a1, a2)-(b1, b2) in integer halving. When a2 > b2 the ends are
(0, 255) and (255, 0). Integer semantics follow the x86 code: 32-bit wrap on imul low
halves, idiv truncates toward zero, the line helper uses unsigned floor division and
clamps to 0..255, the Bezier stepper keeps the low byte. See docs/display.md.
"""

from __future__ import annotations


def _i32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def _tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _slope(ya, yb, xa, xb):  # 0x449680: ((ya - yb) << 16) idiv (xa - xb)
    return _i32(_tdiv((ya - yb) * 0x10000, xa - xb))


def _line(lut, x0, y0, x1, y1):  # 0x449084: fills x0 <= x < x1
    if x0 == x1:
        return
    if y0 == y1:
        for x in range(x0, x1):
            lut[x] = y0 & 0xFF
        return
    if y1 < y0:
        dx, dy = x1 - x0, y0 - y1
        for x in range(x0, x1):
            lut[x] = min(max(y0 - ((x - x0) * dy) // dx, 0), 255)
    else:
        dx, dy = x1 - x0, y1 - y0
        for x in range(x0, x1):
            lut[x] = min(max((x - x0) * dy // dx + y0, 0), 255)


def _step(lut, x0, y0, n, c_sq, c_lin):  # 0x4496b8
    nn = _i32(n * n)
    for k in range(n):
        t1 = _i32(_tdiv(c_sq * _i32(k * k), nn))
        t2 = _i32(_tdiv(c_lin * k, n))
        v = _tdiv(_i32(t1 + t2), 0x10000) + y0
        lut[x0 + k] = v & 0xFF


def _take_alt(ecx, ebx):  # 0x449694: True -> the alternate (swapped-axis) path
    return ebx > ecx if ebx >= 0 else ecx > ebx


def _merge(lut, tmp, start, x_end, y_end):  # 0x449730: inverse table -> forward table
    idx = start
    prev = tmp[idx]
    prev_idx = idx
    idx += 1
    while idx < y_end:
        cur = tmp[idx]
        if prev != cur:
            if prev < cur:
                _line(lut, prev, prev_idx, cur, idx)
            else:
                _line(lut, cur, idx, prev, prev_idx)
        prev, prev_idx = cur, idx
        idx += 1
    if prev == x_end:
        return
    if prev < x_end:
        _line(lut, prev, prev_idx, x_end, y_end)
    else:
        _line(lut, x_end, y_end, prev, prev_idx)


def _seg(lut, x0, y0, cx, cy, x2, y2, first):  # 0x449990 (first) / 0x4497c8 (not first)
    lut[x2 & 0xFF] = y2 & 0xFF
    if x2 <= x0:
        return
    if x2 - x0 <= 2:
        _line(lut, x0, y0, x2, y2)
        return
    while True:
        if cx <= x0:
            if cy == y0:
                _line(lut, x0, y0, x2, y2)
                return
            cx = x0 + 1
            continue
        if x2 <= cx:
            if cy == y2:
                _line(lut, x0, y0, x2, y2)
                return
            cx = x2 - 1
            continue
        break
    s1 = _slope(cy, y0, cx, x0)
    s2 = _slope(y2, cy, x2, cx)
    alt = _take_alt(s1, s2) if first else _take_alt(s2, s1)
    if not alt:
        w, h = x2 - x0, y2 - y0
        if first:
            a = _i32(w * s2)
            c_sq, c_lin = _i32(a - _i32(h * 0x10000)), _i32(_i32(2 * h * 0x10000) - a)
        else:
            a = _i32(w * s1)
            c_sq, c_lin = _i32(_i32(h * 0x10000) - a), a
        _step(lut, x0, y0, w, c_sq, c_lin)
        return
    tmp = [0] * 256
    if y0 <= y2:  # same routine on the swapped axes
        _seg(tmp, y0, x0, cy, cx, y2, x2, first)
        _merge(lut, tmp, y0, x2, y2)
    else:  # the other routine, swapped and reversed
        _seg(tmp, y2, x2, cy, cx, y0, x0, not first)
        _merge(lut, tmp, y2, x0, y0)


def edit_curve(a1, a2, b1, b2):
    """256-entry LUT DEXIS applies for a saved window edit (OriLux values a1, a2, b1, b2)."""
    lut = [0] * 256
    mx = (a1 + b1) >> 1
    q1x, q2x = (a1 + mx) >> 1, (mx + b1) >> 1
    my = (a2 + b2) >> 1
    q1y, q2y = (a2 + my) >> 1, (my + b2) >> 1
    if a2 <= b2:
        _seg(lut, 0, 0, a1, a2, q1x, q1y, True)
        _line(lut, q1x, q1y, q2x, q2y)
        _seg(lut, q2x, q2y, b1, b2, 255, 255, False)
    else:
        _seg(lut, 0, 255, a1, a2, q1x, q1y, True)
        _line(lut, q1x, q1y, q2x, q2y)
        _seg(lut, q2x, q2y, b1, b2, 255, 0, False)
    return lut


def is_identity(a1, a2, b1, b2):
    """True when ``edit_curve`` is the identity, i.e. no saved edit.

    Exactly a1 == a2, b1 == b2 and a1 <= b1 (checked over every such window). A crossed
    window with equal pairs, e.g. (200, 200, 10, 10), is a real curve; DEXIS draws it.
    """
    return a1 == a2 and b1 == b2 and a1 <= b1


def photo_edit(im, lut):
    """DEXIS's photo rendering (dexxdb 0x442d74 with no hue/saturation change).

    The curve goes on luma only: Y = (76 R' + 151 G' + 29 B') >> 8 with each channel's low
    bit dropped, R and B keep their offset from Y, and G is solved back from Y. DEXIS runs
    this on every photo it exports, edited or not, so even the identity curve moves G by up
    to 3 levels. Bit-exact against DEXIS's BMP export of all 13 Test-patient photos.
    """
    import numpy as np
    from PIL import Image

    a = np.asarray(im.convert("RGB"), dtype=np.int32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    y = (76 * (r & 0xFE) + 151 * (g & 0xFE) + 29 * (b & 0xFE)) >> 8
    ly = np.asarray(lut, dtype=np.int32)[y]
    nr = np.clip(r - y + ly, 0, 255)
    nb = np.clip(b - y + ly, 0, 255)
    num = (ly << 8) - 29 * (nb & 0xFE) - 76 * (nr & 0xFE)
    ng = np.clip(np.where(num >= 0, num // 151, -((-num) // 151)), 0, 255)
    return Image.fromarray(np.stack([nr, ng, nb], axis=-1).astype(np.uint8), "RGB")
