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
