import pytest

from .conftest import DATA, FIXTURES, needs_dll


def test_window_lut_identity_when_unedited():
    from dexport.clearvu import window_lut

    assert window_lut(64, 64, 192, 192) is None
    assert window_lut(0, 0, 0, 0) is None
    # crossed equal pairs are a real curve in DEXIS (checked through XimgTryExportFile)
    assert window_lut(200, 200, 10, 10) is not None


def test_window_lut_monotone_and_bounded():
    from dexport.clearvu import window_lut

    lut = window_lut(64, 80, 192, 180)
    assert lut is not None and len(lut) == 256
    assert lut[0] == 0 and lut[255] == 255
    assert all(0 <= v <= 255 for v in lut)
    assert all(b >= a for a, b in zip(lut, lut[1:]))
    # the middle is the straight line through the quarter points of (a1,a2)-(b1,b2)
    assert lut[128] == pytest.approx(80 + 64 * 100 / 128, abs=1)


def test_edit_curve_matches_dexis_palettes():
    """Palettes DEXIS itself wrote (XimgTryExportFile BMP) for 60 windows, incl. edge cases."""
    import json

    from dexport.tonecurve import edit_curve

    data = json.loads((DATA / "edit_curves.json").read_text())
    assert len(data["curves"]) == 60
    for c in data["curves"]:
        assert edit_curve(*c["window"]) == list(bytes.fromhex(c["lut"])), c["window"]


@needs_dll
def test_filter_keeps_size_and_mode(clearvu, xfile):
    im = xfile.read(FIXTURES / "DCQ10.DEX")
    out = clearvu.filter(im)
    assert out.size == im.size and out.mode == "L"
    assert out.tobytes() != im.tobytes()  # it did something


@needs_dll
def test_rgb_passes_through(clearvu):
    from PIL import Image

    im = Image.new("RGB", (8, 8), (1, 2, 3))
    assert clearvu.filter(im) is im


def test_photo_edit_matches_dexis_pixels():
    """Raw -> DEXIS pixel pairs from DEXIS's own export of three photos (one unedited)."""
    import json

    from PIL import Image

    from dexport.tonecurve import edit_curve, photo_edit

    data = json.loads((DATA / "photo_pairs.json").read_text())
    assert len(data["cases"]) == 3
    for case in data["cases"]:
        raw = [tuple(p[0]) for p in case["pairs"]]
        want = [tuple(p[1]) for p in case["pairs"]]
        im = Image.new("RGB", (len(raw), 1))
        im.putdata(raw)
        got = photo_edit(im, edit_curve(*case["window"])).tobytes()
        assert got == bytes(v for px in want for v in px), case["window"]


@needs_dll
def test_display_routes_photos_through_photo_edit(clearvu):
    from pathlib import Path

    from PIL import Image

    from dexport.tonecurve import edit_curve, photo_edit
    from dexport.xfile import ImageMeta

    im = Image.new("RGB", (4, 2), (200, 120, 40))
    meta = ImageMeta(Path("x"), lux=(40, 40, 168, 216, 0, 0), rotation=1)
    want = photo_edit(im, edit_curve(40, 40, 168, 216)).tobytes()
    assert clearvu.display(im, meta).tobytes() == want
    no_orilux = ImageMeta(Path("x"))
    assert clearvu.display(im, no_orilux).tobytes() == im.tobytes()
