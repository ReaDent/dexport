import pytest

from dexport.teeth import fdi_to_universal, teeth_label


@pytest.mark.parametrize(
    "fdi,uni",
    [
        (18, "1"),
        (11, "8"),
        (21, "9"),
        (28, "16"),
        (38, "17"),
        (31, "24"),
        (41, "25"),
        (48, "32"),
        (55, "A"),
        (51, "E"),
        (61, "F"),
        (65, "J"),
        (75, "K"),
        (71, "O"),
        (81, "P"),
        (85, "T"),
    ],
)
def test_fdi_to_universal(fdi, uni):
    assert fdi_to_universal(fdi) == uni


@pytest.mark.parametrize(
    "code,label",
    [
        (0, ("", "")),
        (36, ("PA", "19")),
        (21, ("PA", "9")),
        (23, ("PA", "11")),
        (1121, ("PA", "8-9")),
        (2223, ("PA", "10-11")),
        (3435, ("PA", "20-21")),
        (1846, ("BW", "1-3 30-32")),  # Dexis.ini series 1-30
        (2436, ("BW", "12-14 19-21")),  # series 12-19
        (2638, ("BW", "14-16 17-19")),  # series 14-17
        (1644, ("BW", "3-5 28-30")),  # series 3-28
        (99, ("", "")),
        (1899, ("", "")),
    ],
)
def test_teeth_label(code, label):
    assert teeth_label(code) == label


def test_teeth_fdi_single_and_runs():
    from dexport.teeth import teeth_fdi

    assert teeth_fdi(0) == []
    assert teeth_fdi(36) == [36]
    assert teeth_fdi(1121) == [11, 21]  # upper centrals, across the midline
    assert teeth_fdi(2427) == [24, 25, 26, 27]
    assert teeth_fdi(4131) == [41, 31]
    assert teeth_fdi(1846) == [18, 17, 16, 48, 47, 46]  # right molar bitewing
    assert teeth_fdi(2638) == [26, 27, 28, 36, 37, 38]
    assert teeth_fdi(5361) == [53, 52, 51, 61]  # primary run
    assert teeth_fdi(2861) == [28, 61]  # mixed dentition: corners only
    assert teeth_fdi(3972) == [72]  # 39 is not a tooth; 72 is
    assert teeth_fdi(3949) == []  # neither corner is a tooth


def test_teeth_fdi_matches_teeth_label_span():
    from dexport.teeth import fdi_to_universal, teeth_fdi, teeth_label

    perm = [q * 10 + t for q in (1, 2, 3, 4) for t in range(1, 9)]
    for a in perm:
        for b in perm:
            if a == b:
                continue
            kind, label = teeth_label(a * 100 + b)
            got = {int(fdi_to_universal(t)) for t in teeth_fdi(a * 100 + b)}
            want = set()
            for part in label.split():
                lo, _, hi = part.partition("-")
                want |= set(range(int(lo), int(hi or lo) + 1))
            if kind == "BW" and "-" not in label:
                # diagonal corners teeth_label leaves unexpanded: still covered
                assert want <= got, (a, b, label)
            else:
                assert got == want, (a, b, label)
