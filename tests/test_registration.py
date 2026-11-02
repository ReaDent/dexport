import pytest

from dexport import registration as reg


def test_env_wins(monkeypatch, tmp_path):
    f = tmp_path / "r.txt"
    f.write_text("FILE:2\n")
    monkeypatch.setenv(reg.ENV_FILE, str(f))
    monkeypatch.setenv(reg.ENV, "ENVNAME:1")
    assert reg.load() == ("ENVNAME", "1")


def test_file_with_comment(monkeypatch, tmp_path):
    f = tmp_path / "r.txt"
    f.write_text("# my install\n  NAME : 123 \n")
    monkeypatch.delenv(reg.ENV, raising=False)
    monkeypatch.setenv(reg.ENV_FILE, str(f))
    assert reg.load() == ("NAME", "123")
    assert reg.configured()


def test_missing_names_the_file(monkeypatch, tmp_path):
    monkeypatch.delenv(reg.ENV, raising=False)
    monkeypatch.setenv(reg.ENV_FILE, str(tmp_path / "none.txt"))
    with pytest.raises(reg.RegistrationMissing, match="none.txt"):
        reg.load()
    assert not reg.configured()


@pytest.mark.parametrize(
    "raw",
    [
        b"NAME:123\r\n",  # plain
        b"\xef\xbb\xbfNAME:123\r\n",  # UTF-8 with BOM (Notepad, Set-Content -Encoding UTF8)
        "NAME:123\r\n".encode("utf-16"),  # UTF-16 LE with BOM (PowerShell 5.1 >)
        b"\xfe\xff" + "NAME:123\r\n".encode("utf-16-be"),  # UTF-16 BE with BOM
    ],
)
def test_windows_encodings(monkeypatch, tmp_path, raw):
    f = tmp_path / "r.txt"
    f.write_bytes(raw)
    monkeypatch.delenv(reg.ENV, raising=False)
    monkeypatch.setenv(reg.ENV_FILE, str(f))
    assert reg.load() == ("NAME", "123")


def test_unreadable_is_missing_not_a_crash(monkeypatch, tmp_path):
    f = tmp_path / "r.txt"
    f.write_bytes(b"\xff\xff\xff\x00garbage")
    monkeypatch.delenv(reg.ENV, raising=False)
    monkeypatch.setenv(reg.ENV_FILE, str(f))
    with pytest.raises(reg.RegistrationMissing, match="plain text"):
        reg.load()
    assert not reg.configured()


@pytest.mark.parametrize("bad", ["", "NAMEONLY", ":123", "NAME:"])
def test_malformed(bad):
    with pytest.raises(reg.RegistrationMissing):
        reg.parse(bad)
