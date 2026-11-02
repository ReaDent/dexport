"""Lay x-rays out the way DEXIS mounts them: upper periapicals, bitewings, lower periapicals.

DEXIS places each image at a "home" position from its tooth code (manual, Selection and
Navigation) and has no stored mount template. The closest thing in DEXIS.EXE is its
film-scan templates, three rows of tooth codes with cut lines in percent of the width:

    upper  1816 20 1614 35 1312 45 1121 55 2223 65 2426 80 2628
    bw     1846 20 1644 42 1232 58 2436 80 2638
    lower  4846 20 4644 35 4342 45 4131 55 3233 65 3436 80 3638

so the patient's right sits on the viewer's left, as in a labial mount. Its "Export FMX
as one image" defaults to a 2000x900 canvas with a 17 px title bar per image
(``fmxexport=2000 900 17 0 15`` in DEXIS.EXE). This module follows that: each image goes
in the row its teeth belong to, centred over its place along the arch, with a title bar
naming the teeth and the date. Images with no tooth code (pans, cephs, imports) go in a
last row. Exact pixel positions are ours, not DEXIS's.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .teeth import teeth_label

ROWS = ("upper", "bw", "lower", "other")
ARCH_SLOTS = 16  # tooth positions across one arch, patient's right molar first


def arch_pos(fdi: int) -> tuple[str, int]:
    """(arch, position 0..15 along it, viewer's left first) for one FDI tooth.

    Primary teeth (quadrants 5 to 8) take the position of the permanent tooth with the
    same number in the matching quadrant, which is close enough for a mount.
    """
    q, t = divmod(fdi, 10)
    if not 1 <= t <= 8 or q not in range(1, 9) or (q > 4 and t > 5):
        raise ValueError(f"not an FDI tooth: {fdi}")
    side = {1: "R", 2: "L", 3: "L", 4: "R", 5: "R", 6: "L", 7: "L", 8: "R"}[q]
    arch = "upper" if q in (1, 2, 5, 6) else "lower"
    return arch, (8 - t) if side == "R" else (7 + t)


def slot(code: int) -> tuple[str, float]:
    """(row, centre along the arch) for a DEXIS tooth code; ('other', 0) if it has none."""
    try:
        if 0 < code < 100:
            arch, p = arch_pos(code)
            return arch, float(p)
        if 100 <= code < 10000:
            (a1, p1), (a2, p2) = arch_pos(code // 100), arch_pos(code % 100)
            return (a1 if a1 == a2 else "bw"), (p1 + p2) / 2
    except ValueError:
        pass
    return "other", 0.0


@dataclass
class Tile:
    # Already upright and processed for display. Anterior PAs are taken vertical, so they
    # arrive portrait and mount narrower; nothing here rotates an image.
    image: Image.Image
    teeth: int
    day: dt.date | None


def caption(t: Tile) -> str:
    kind, teeth = teeth_label(t.teeth)
    label = f"{kind} {teeth}".strip() or "X-ray"
    return f"{label}   {t.day.strftime('%m/%d/%Y')}" if t.day else label


def place(widths: list[int], centres: list[float], total: int, gap: int) -> list[int]:
    """Left edges for boxes that should sit over their arch centres without overlapping.

    Each box first goes where its centre asks; a left-to-right pass then pushes overlaps
    right, and a right-to-left pass pulls anything past the edge back in."""
    xs = [
        round((c + 0.5) / ARCH_SLOTS * total - w / 2) for w, c in zip(widths, centres)
    ]
    edge = 0
    for i, w in enumerate(widths):
        xs[i] = max(xs[i], edge)
        edge = xs[i] + w + gap
    edge = total
    for i in range(len(widths) - 1, -1, -1):
        xs[i] = min(xs[i], edge - widths[i])
        edge = xs[i] - gap
    return [max(0, x) for x in xs]


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def compose(
    tiles: list[Tile],
    row_height: int = 480,
    title: int = 30,
    gap: int = 12,
    header: str = "",
) -> Image.Image:
    """One mounted sheet of the tiles: rows upper, bitewing, lower, then everything else."""
    if not tiles:
        raise ValueError("nothing to mount")
    rows: dict[str, list[tuple[float, Tile]]] = {r: [] for r in ROWS}
    for t in tiles:
        r, c = slot(t.teeth)
        rows[r].append((c, t))
    rows["other"].sort(key=lambda ct: ct[1].day or dt.date.min)
    for r in ROWS[:3]:
        rows[r].sort(key=lambda ct: ct[0])

    def scaled(t: Tile) -> Image.Image:
        w, h = t.image.size
        return t.image.resize(
            (max(1, round(w * row_height / h)), row_height), Image.Resampling.LANCZOS
        )

    built = {r: [(c, t, scaled(t)) for c, t in rows[r]] for r in ROWS if rows[r]}
    width = max(
        sum(im.width for _, _, im in items) + gap * (len(items) - 1)
        for items in built.values()
    )
    width = max(width, round(row_height * 3))
    font = _font(round(title * 0.6)) if title else None  # title=0: a bare preview
    head = round(title * 1.7) if header else 0
    band = title + row_height
    sheet = Image.new("L", (width + 2 * gap, head + len(built) * (band + gap) + gap), 0)
    draw = ImageDraw.Draw(sheet)
    if header:
        draw.text((gap, gap), header, fill=255, font=_font(round(title * 0.95)))
    y = head + gap
    for r, items in built.items():
        widths = [im.width for _, _, im in items]
        if r == "other":
            xs, x = [], 0
            for w in widths:
                xs.append(x)
                x += w + gap
        else:
            xs = place(widths, [c for c, _, _ in items], width, gap)
        for x, (_, t, im) in zip(xs, items):
            x += gap
            if font:
                draw.rectangle((x, y, x + im.width - 1, y + title - 1), fill=60)
                draw.text(
                    (x + 6, y + (title - font.size) // 2 - 1),
                    caption(t),
                    fill=255,
                    font=font,
                )
            sheet.paste(im.convert("L"), (x, y + title))
        y += band + gap
    return sheet
