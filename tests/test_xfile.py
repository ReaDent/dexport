"""Decode and metadata against the sample images DEXIS ships in C:\\DEXIS\\Simulation."""

import hashlib
import json
from pathlib import Path

import pytest

from .conftest import FIXTURES, needs_dll

GOLDEN = Path(__file__).parent / "golden.json"


def pixel_hash(im) -> str:
    return hashlib.sha256(im.tobytes()).hexdigest()[:16]


@needs_dll
def test_every_fixture_decodes(xfile):
    for dex in sorted(FIXTURES.glob("*.DEX")):
        im = xfile.read(dex)
        assert im.mode in ("L", "RGB"), dex.name
        assert im.width > 100 and im.height > 100, dex.name


@needs_dll
def test_metadata_fields(xfile):
    m = xfile.meta(FIXTURES / "DCQ10.DEX")
    assert m.bps in (8, 24)
    assert m.kind in ("xray", "photo")
    assert m.frames >= 1
    assert m.rotation is None or 0 <= m.rotation <= 4
    d = m.as_dict()
    assert set(d) >= {"kind", "captured", "edited", "type_name", "path"}


@needs_dll
def test_header_size_never_smaller_than_decoded(xfile):
    for dex in sorted(FIXTURES.glob("*.DEX"))[:10]:
        m = xfile.meta(dex)
        im = xfile.read(dex)
        assert m.header_width >= im.width and m.header_height >= im.height, dex.name


@needs_dll
def test_golden_pixel_hashes(xfile):
    """A DLL update or a stride bug shows up here. Hashes are of the 48 .DEX samples a
    DEXIS 9.5.3 install ships; samples missing from an install are skipped."""
    golden = json.loads(GOLDEN.read_text())
    present = {name: h for name, h in golden.items() if (FIXTURES / name).exists()}
    if not present:
        pytest.skip("none of the golden samples are installed")
    current = {name: pixel_hash(xfile.read(FIXTURES / name)) for name in present}
    assert current == present


@needs_dll
def test_decode_error_on_missing_file(xfile):
    from dexport.xfile import DecodeError

    with pytest.raises(DecodeError):
        xfile.read(FIXTURES / "nope.DEX")


def test_upright_codes():
    from PIL import Image

    from dexport.xfile import upright

    im = Image.new("L", (4, 2))
    assert upright(im, None).size == (4, 2)
    assert upright(im, 0).size == (4, 2)
    assert upright(im, 1).size == (4, 2)
    assert upright(im, 2).size == (2, 4)
    assert upright(im, 3).size == (4, 2)
    assert upright(im, 4).size == (2, 4)


def test_captured_parsing():
    from dexport.xfile import ImageMeta

    m = ImageMeta(Path("x"), acq_date="20260304", acq_time="122225")
    assert m.captured.isoformat() == "2026-03-04T12:22:25"
    m = ImageMeta(Path("x"), acq_date="20230802", acq_time="1051")
    assert m.captured.isoformat() == "2023-08-02T10:51:00"
    m = ImageMeta(Path("x"), acq_date="20230802", acq_time="")
    assert m.captured.isoformat() == "2023-08-02T00:00:00"
    assert ImageMeta(Path("x")).captured is None


def test_edited_flag():
    from dexport.xfile import ImageMeta

    assert not ImageMeta(Path("x"), lux=(64, 64, 192, 192, 0, 0)).edited
    assert ImageMeta(Path("x"), lux=(64, 80, 192, 192, 0, 0)).edited
    assert ImageMeta(Path("x"), lux=(200, 200, 10, 10, 0, 0)).edited  # crossed window
    assert not ImageMeta(Path("x")).edited


def test_struct_to_image_24bit_bgr_with_stride_padding():
    import struct

    from dexport.xfile import struct_to_image

    w, h, stride = 2, 2, 8  # 6 bytes of pixels per row, padded to 8
    rows = [bytes([255, 0, 0, 0, 255, 0, 9, 9]), bytes([0, 0, 255, 7, 7, 7, 9, 9])]
    header = struct.pack("<5iI", w, h, 24, 0, stride, 0)
    im = struct_to_image(header, b"".join(rows))
    assert im.mode == "RGB" and im.size == (2, 2)
    assert im.getpixel((0, 0)) == (0, 0, 255)  # BGR -> RGB
    assert im.getpixel((1, 0)) == (0, 255, 0)
    assert im.getpixel((0, 1)) == (255, 0, 0)
    assert im.getpixel((1, 1)) == (7, 7, 7)


def test_struct_to_image_8bit_and_bad_bpp():
    import struct

    import pytest

    from dexport.xfile import struct_to_image

    header = struct.pack("<5iI", 3, 1, 8, 0, 4, 0)
    im = struct_to_image(header, bytes([1, 2, 3, 0]))
    assert im.mode == "L" and im.tobytes() == bytes([1, 2, 3])
    with pytest.raises(ValueError):
        struct_to_image(struct.pack("<5iI", 1, 1, 16, 0, 2, 0), b"\0\0")


@needs_dll
def test_thumbnail_divisor_and_size(xfile):
    full = xfile.read(FIXTURES / "DCQ10.DEX")  # 792x632
    for max_size, scale in ((64, 4), (256, 2), (1000, 1)):
        im, s = xfile.thumbnail(FIXTURES / "DCQ10.DEX", max_size)
        assert s == scale, max_size
        assert im.size == (full.width // scale, full.height // scale), max_size
        assert im.mode == full.mode
    im, _ = xfile.thumbnail(FIXTURES / "DCQ10.DEX", 1000)
    assert pixel_hash(im) == pixel_hash(full)


@needs_dll
def test_check_crc(xfile, tmp_path):
    data = (FIXTURES / "DCQ10.DEX").read_bytes()
    assert xfile.check_crc(FIXTURES / "DCQ10.DEX") == 0
    flipped = bytearray(data)
    flipped[600] ^= 0xFF
    (tmp_path / "flip.DEX").write_bytes(flipped)
    assert xfile.check_crc(tmp_path / "flip.DEX") == 1
    (tmp_path / "half.DEX").write_bytes(data[: len(data) // 2])
    assert xfile.check_crc(tmp_path / "half.DEX") == -1


@needs_dll
def test_black_white_absent_on_samples(xfile):
    assert xfile.black_white(FIXTURES / "DCQ10.DEX") is None
