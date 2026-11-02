from pathlib import Path

from dexport.catalog import DexisRoot, list_indexed


def test_patient_folder_layout(tmp_path):
    assert (
        DexisRoot(tmp_path).patient_folder(12345)
        == tmp_path / "1" / "2" / "3" / "4" / "5"
    )
    assert (
        DexisRoot(tmp_path).patient_folder(12) == tmp_path / "0" / "0" / "0" / "1" / "2"
    )


def test_indexes_are_the_source_of_truth(tmp_path):
    root = tmp_path
    folder = root / "1" / "2" / "3" / "4" / "5"
    folder.mkdir(parents=True)
    (folder / "000001.DEX").write_bytes(b"x")
    (folder / "p000002.DEX").write_bytes(b"x")
    (folder / "000003.DEX").write_bytes(b"x")  # on disk, not indexed
    (folder / "DEXIS.dat").write_text(
        "junk 1/2/3/4/5/000001.DEX\nmissing 1/2/3/4/5/000009.DEX\n"
    )
    (folder / "DEVIS.dat").write_text("x 1/2/3/4/5/p000002.DEX\n")
    files = list_indexed(root, folder)
    assert [(f.path.name, f.source) for f in files] == [
        ("000001.DEX", "xray"),
        ("p000002.DEX", "photo"),
    ]
    assert DexisRoot(root).images(12345) == files


def test_missing_patient_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        DexisRoot(tmp_path).images(1)


def test_listed_twice_counts_once(tmp_path):
    folder = tmp_path / "0" / "0" / "0" / "0" / "1"
    folder.mkdir(parents=True)
    (folder / "000001.DEX").write_bytes(b"x")
    (folder / "DEXIS.dat").write_text("a 0/0/0/0/1/000001.DEX\nb 0/0/0/0/1/000001.DEX\n")
    (folder / "DEVIS.dat").write_text("c 0/0/0/0/1/000001.DEX\n")
    files = list_indexed(tmp_path, folder)
    assert len(files) == 1 and files[0].source == "xray"
