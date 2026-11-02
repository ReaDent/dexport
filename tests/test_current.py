from dexport.current import (
    OpenPatient,
    current_patient,
    net_lock_holder,
    open_patients,
    pat_file,
)


def test_current_patient_reads_the_host_pat_file(tmp_path):
    (tmp_path / "WS-01.pat").write_bytes(b"12345\r\n")  # zero-padded, CRLF
    assert current_patient(tmp_path, "WS-01") == 12345


def test_current_patient_zero_pad_is_stripped(tmp_path):
    (tmp_path / "WS-01.pat").write_bytes(b"00012\r\n")
    assert current_patient(tmp_path, "WS-01") == 12


def test_current_patient_none_when_absent_or_empty(tmp_path):
    assert current_patient(tmp_path, "NOBODY") is None
    (tmp_path / "EMPTY.pat").write_bytes(b"\r\n")
    assert current_patient(tmp_path, "EMPTY") is None
    (tmp_path / "JUNK.pat").write_text("not-an-id")
    assert current_patient(tmp_path, "JUNK") is None


def test_pat_file_defaults_to_this_host(tmp_path):
    # no host given: filename is <hostname>.pat, whatever this machine is called
    assert pat_file(tmp_path).suffix == ".pat"
    assert pat_file(tmp_path).parent == tmp_path


def test_open_patients_lists_every_workstation(tmp_path):
    (tmp_path / "WS-01.pat").write_bytes(b"12345\r\n")
    (tmp_path / "WS-02.pat").write_bytes(b"00012\r\n")
    (tmp_path / "BAD.pat").write_text("")  # skipped
    assert open_patients(tmp_path) == [
        OpenPatient("WS-01", 12345),
        OpenPatient("WS-02", 12),
    ]


def test_net_lock_holder(tmp_path):
    assert net_lock_holder(tmp_path) is None
    (tmp_path / "DEXnet.lck").write_bytes(b"WS-01")  # no trailing newline
    assert net_lock_holder(tmp_path) == "WS-01"
