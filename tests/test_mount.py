import datetime as dt

from PIL import Image

from dexport.mount import Tile, compose, place, slot

# Dexis.ini [PROGRAMS] series1: the 18-image full-mouth series DEXIS captures
FMX = [
    1816,
    1614,
    3638,
    3436,
    2628,
    2426,
    4846,
    4644,
    1412,
    1121,
    2224,
    3234,
    4131,
    4442,
    1846,
    1644,
    2436,
    2638,
]


def test_slots_follow_the_dexis_scan_template_rows():
    rows = {c: slot(c)[0] for c in FMX}
    assert [c for c in FMX if rows[c] == "upper"] == [
        1816,
        1614,
        2628,
        2426,
        1412,
        1121,
        2224,
    ]
    assert [c for c in FMX if rows[c] == "lower"] == [
        3638,
        3436,
        4846,
        4644,
        3234,
        4131,
        4442,
    ]
    assert [c for c in FMX if rows[c] == "bw"] == [1846, 1644, 2436, 2638]
    # patient's right on the viewer's left, as DEXIS's template 1816 ... 2628
    upper = sorted((c for c in FMX if rows[c] == "upper"), key=lambda c: slot(c)[1])
    assert upper == [1816, 1614, 1412, 1121, 2224, 2426, 2628]
    lower = sorted((c for c in FMX if rows[c] == "lower"), key=lambda c: slot(c)[1])
    assert lower == [4846, 4644, 4442, 4131, 3234, 3436, 3638]
    bw = sorted((c for c in FMX if rows[c] == "bw"), key=lambda c: slot(c)[1])
    assert bw == [1846, 1644, 2436, 2638]


def test_single_teeth_primary_and_unknown_codes():
    assert slot(36) == ("lower", 13.0)
    assert slot(18) == ("upper", 0.0)
    assert slot(5118)[0] == "upper"  # primary E with permanent 18
    assert slot(0) == ("other", 0.0)
    assert slot(3739) == ("other", 0.0)  # 39 is not a tooth
    assert slot(12345) == ("other", 0.0)


def test_place_keeps_order_and_bounds_without_overlap():
    xs = place([300, 300, 300, 300], [0, 3, 12, 15], 2000, 10)
    assert xs == sorted(xs)
    assert xs[0] == 0 and xs[-1] + 300 <= 2000
    assert all(b - a >= 310 for a, b in zip(xs, xs[1:]))
    # right-side bitewings stay left of centre, left-side ones right of it
    assert xs[1] + 300 < 1000 < xs[2]
    crowded = place([600] * 4, [7, 7.5, 8, 8.5], 2430, 10)
    assert all(b - a >= 610 for a, b in zip(crowded, crowded[1:]))


def _tile(code, w=640, h=480, day=dt.date(2026, 3, 4), v=128):
    return Tile(Image.new("L", (w, h), v), code, day)


def test_compose_full_mouth_three_rows():
    tiles = []
    for c in FMX:
        anterior = c in (1412, 1121, 2224, 4442, 4131, 3234)
        tiles.append(
            _tile(c, *((360, 480) if anterior else (640, 480)))
        )  # anteriors taken vertical
    sheet = compose(tiles, row_height=240, title=20, gap=10, header="Pat Test")
    assert sheet.mode == "L"
    head = round(20 * 1.7)
    assert sheet.height == head + 3 * (20 + 240 + 10) + 10
    # anterior PAs mount narrower: 4 posteriors at 320 + 3 anteriors at 180 + gaps
    assert sheet.width == 4 * 320 + 3 * 180 + 6 * 10 + 2 * 10


def test_compose_puts_untoothed_images_last():
    sheet = compose(
        [_tile(1846), _tile(0, 900, 480, None)], row_height=100, title=10, gap=4
    )
    assert sheet.height == 2 * (10 + 100 + 4) + 4
