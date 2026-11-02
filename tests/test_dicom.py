"""DICOM output. The pure tests build datasets from synthetic metadata; the DLL tests export
DEXIS's own Simulation samples (vendor demo data, no patients)."""

import datetime as dt
from pathlib import Path

import pydicom
import pytest
from PIL import Image, TiffImagePlugin

from dexport import dicom
from dexport import dicom_codes as codes
from dexport.xfile import ImageMeta

from .conftest import FIXTURES, needs_dll

FIXED = dt.datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001 (DICOM times are local)


def xray_meta(**kw) -> ImageMeta:
    base = {
        "path": Path("000017.DEX"),
        "bps": 8,
        "type": 5,
        "teeth": 1846,
        "acq_date": "20240305",
        "acq_time": "101112",
        "rotation": 1,
        "lux": (64, 64, 192, 192, 0, 0),
        "pixel_spacing": (38840, 39070),
    }
    base.update(kw)
    return ImageMeta(**base)


def build(meta, im=None, identity=None, uids=None):
    im = im or Image.new("L", (60, 40), 100)
    identity = identity or dicom.Identity("12345", "Sample^Pat", "19900102")
    return dicom.dataset(im, meta, identity, uids or dicom.UidMaker(), model="Ti2")


def roundtrip(ds, tmp_path) -> pydicom.Dataset:
    out = tmp_path / "x.dcm"
    dicom.write(ds, out)
    return pydicom.dcmread(out)


def test_intraoral_xray_is_io_for_presentation(tmp_path):
    ds = roundtrip(build(xray_meta()), tmp_path)
    assert ds.SOPClassUID == dicom.IO_PRESENTATION
    assert ds.file_meta.TransferSyntaxUID == pydicom.uid.ExplicitVRLittleEndian
    assert ds.Modality == "IO" and ds.PresentationIntentType == "FOR PRESENTATION"
    assert (ds.Rows, ds.Columns) == (40, 60)
    assert (ds.PhotometricInterpretation, ds.BitsStored) == ("MONOCHROME2", 8)
    assert list(ds.ImageType) == ["ORIGINAL", "PRIMARY", ""]
    assert (ds.WindowCenter, ds.WindowWidth) == (128, 256)
    assert ds.PixelIntensityRelationshipSign == -1
    assert list(ds.PatientOrientation) == ["L", "F"]
    assert ds.PositionerType == "NONE"
    assert ds.pixel_array.max() == 100
    assert (ds.StudyDate, ds.StudyTime) == ("20240305", "101112")
    assert (ds.PatientID, ds.PatientName, ds.PatientBirthDate) == (
        "12345",
        "Sample^Pat",
        "19900102",
    )
    assert (ds.Manufacturer, ds.ManufacturerModelName) == ("DEXIS", "Ti2")
    assert ds.InstanceNumber == 17


def test_spacing_matches_dexis_order():
    # DEXIS writes the DLL's (first, second) nanometre pair as [second, first] mm
    ds = build(xray_meta(pixel_spacing=(38840, 39070)))
    assert [str(v) for v in ds.ImagerPixelSpacing] == ["0.03907", "0.03884"]
    assert ds.PixelSpacing == ds.ImagerPixelSpacing
    assert [
        str(v)
        for v in build(xray_meta(pixel_spacing=(19500, 19500))).ImagerPixelSpacing
    ] == [
        "0.0195",
        "0.0195",
    ]


def test_bitewing_anatomy():
    ds = build(xray_meta(teeth=1846))
    assert ds.ImageLaterality == "R"
    region = ds.AnatomicRegionSequence[0]
    assert (region.CodeValue, region.CodeMeaning) == ("661005", "Jaw region")
    teeth = ds.PrimaryAnatomicStructureSequence
    assert [t.CodeValue for t in teeth] == [
        codes.TEETH[t][0] for t in (18, 17, 16, 48, 47, 46)
    ]
    assert {t.CodingSchemeDesignator for t in teeth} == {"SCT"}


@pytest.mark.parametrize(
    ("teeth", "laterality", "region"),
    [
        (1121, "B", codes.MAXILLA),  # across the midline
        (21, "L", codes.MAXILLA),
        (36, "L", codes.MANDIBLE),
        (4644, "R", codes.MANDIBLE),
        (0, "B", codes.TEETH_GUMS),  # DEXIS recorded no teeth
    ],
)
def test_laterality_and_region(teeth, laterality, region):
    ds = build(xray_meta(teeth=teeth))
    assert ds.ImageLaterality == laterality
    assert ds.AnatomicRegionSequence[0].CodeValue == region[0]
    assert ("PrimaryAnatomicStructureSequence" in ds) == bool(teeth)


def test_tooth_36_is_the_standard_example():
    ds = build(xray_meta(teeth=36))
    item = ds.PrimaryAnatomicStructureSequence[0]
    assert (item.CodeValue, item.CodingSchemeDesignator, item.CodeMeaning) == (
        "866006002",
        "SCT",
        "Mandibular left first molar tooth",
    )


def test_code_table_covers_every_tooth():
    permanent = {q * 10 + t for q in (1, 2, 3, 4) for t in range(1, 9)}
    deciduous = {q * 10 + t for q in (5, 6, 7, 8) for t in range(1, 6)}
    assert set(codes.TEETH) == permanent | deciduous


def test_edited_xray_is_derived():
    ds = build(xray_meta(lux=(72, 61, 200, 255, 0, 0)))
    assert list(ds.ImageType) == ["DERIVED", "PRIMARY", ""]


def test_pixels_bake_the_edit_and_turn_upright():
    from dexport.tonecurve import edit_curve

    raw = Image.linear_gradient("L").resize((64, 32))
    meta = xray_meta(lux=(72, 61, 200, 255, 0, 0), rotation=4)
    out = dicom.pixels(raw, meta)
    want = raw.point(edit_curve(72, 61, 200, 255)).transpose(Image.Transpose.ROTATE_90)
    assert out.size == (32, 64) and out.tobytes() == want.tobytes()


@pytest.mark.parametrize(
    "meta",
    [
        xray_meta(type=6, teeth=0),  # pan, ceph or scan "from another system"
        xray_meta(pixel_spacing=None),  # no sensor pitch
    ],
)
def test_other_xrays_are_secondary_capture(meta, tmp_path):
    ds = roundtrip(build(meta), tmp_path)
    assert ds.SOPClassUID == dicom.SECONDARY_CAPTURE
    assert (ds.Modality, ds.ConversionType) == ("OT", "DI")
    assert "ImageLaterality" not in ds


def test_photo_is_rgb_secondary_capture(tmp_path):
    meta = xray_meta(bps=24, type=9, teeth=0, pixel_spacing=None)
    ds = roundtrip(build(meta, Image.new("RGB", (8, 6), (10, 20, 30))), tmp_path)
    assert ds.SOPClassUID == dicom.SECONDARY_CAPTURE
    assert (ds.Modality, ds.PhotometricInterpretation, ds.SamplesPerPixel) == (
        "XC",
        "RGB",
        3,
    )
    assert ds.PlanarConfiguration == 0
    assert tuple(ds.pixel_array[0, 0]) == (10, 20, 30)


def test_uids_are_stable_and_grouped():
    a, b = build(xray_meta()), build(xray_meta())
    assert (
        a.SOPInstanceUID == b.SOPInstanceUID
        and a.StudyInstanceUID == b.StudyInstanceUID
    )
    other = build(xray_meta(path=Path("000018.DEX")))
    assert other.SOPInstanceUID != a.SOPInstanceUID
    assert other.StudyInstanceUID == a.StudyInstanceUID  # same patient, same day
    assert other.SeriesInstanceUID == a.SeriesInstanceUID
    next_visit = build(xray_meta(acq_date="20240306"))
    assert next_visit.StudyInstanceUID != a.StudyInstanceUID
    assert a.SOPInstanceUID.startswith("2.25.")


def test_anonymized(tmp_path):
    uids = dicom.UidMaker.anonymous()
    ds = roundtrip(build(xray_meta(), identity=dicom.Identity(), uids=uids), tmp_path)
    assert (ds.PatientName, ds.PatientID, ds.PatientBirthDate) == ("", "", "")
    assert ds.PatientIdentityRemoved == "YES"
    # salted, so the UIDs cannot be recomputed from a guessed patient ID
    assert (
        ds.SOPInstanceUID
        != build(xray_meta(), identity=dicom.Identity()).SOPInstanceUID
    )


def test_undated_file_falls_back_to_file_date():
    ds = dicom.dataset(
        Image.new("L", (4, 4)),
        xray_meta(acq_date="", acq_time=""),
        dicom.Identity(),
        dicom.UidMaker(),
        file_date=FIXED,
    )
    assert (ds.StudyDate, ds.StudyTime) == ("20200102", "030405")


def tagged_tiff(path: Path, tags: dict) -> Path:
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    for tag, (value, typ) in tags.items():
        ifd[tag] = value
        ifd.tagtype[tag] = typ
    Image.new("L", (4, 4)).save(path, "TIFF", tiffinfo=ifd)
    return path


def test_read_identity_from_dexis_tags(tmp_path):
    f = tagged_tiff(
        tmp_path / "a.DEX",
        {
            1792: (777, 4),
            1793: ("Sample\x00\x00\x00", 2),
            1794: ("Pat\x00\x00", 2),
            1795: ("01/02/1990\x00", 2),
            1817: ("DEXIS Ti2#0000000\x00", 2),
        },
    )
    assert dicom.read_identity(f) == dicom.Identity("777", "Sample^Pat", "19900102")
    assert dicom.read_identity(f, patient_id=42).patient_id == "42"  # folder ID wins
    assert dicom.device_model(f) == "Ti2"


def test_read_identity_missing_tags(tmp_path):
    f = tagged_tiff(tmp_path / "b.DEX", {1792: (0, 4)})
    assert dicom.read_identity(f) == dicom.Identity()
    assert dicom.read_identity(tmp_path / "missing.DEX") == dicom.Identity()


# -- through the DLL, on the Simulation samples ---------------------------------------------


@needs_dll
def test_export_simulation_intraoral(tmp_path):
    from dexport.export import Exporter
    from dexport.tonecurve import edit_curve
    from dexport.xfile import Xfile, upright

    src = FIXTURES / "DCQ47.DEX"  # an edited x-ray: lux (80, 93, 208, 235)
    ex = Exporter(display=False)
    r = ex.export(src, tmp_path / "DCQ47.dcm", "dcm")
    ds = pydicom.dcmread(r.dest)
    assert ds.SOPClassUID == dicom.IO_PRESENTATION
    xf = Xfile()
    m = xf.meta(src)
    want = upright(xf.read(src).point(edit_curve(*m.lux[:4])), m.rotation)
    assert (ds.Columns, ds.Rows) == want.size
    assert ds.pixel_array.tobytes() == want.tobytes()
    assert ds.ImageLaterality == "R" and ds.ImageType[0] == "DERIVED"
    assert str(ds.PatientName) == "Demo Cat"  # DEXIS's demo patient


@needs_dll
def test_export_simulation_pan_is_secondary_capture(tmp_path):
    from dexport.export import Exporter

    r = Exporter(display=False, anonymize=True).export(
        FIXTURES / "SimuPan.Dex", tmp_path / "pan.dcm", "dcm"
    )
    ds = pydicom.dcmread(r.dest)
    assert ds.SOPClassUID == dicom.SECONDARY_CAPTURE
    assert ds.PatientName == "" and ds.PatientIdentityRemoved == "YES"


def test_each_modality_gets_its_own_series():
    io = build(xray_meta())
    pan = build(xray_meta(type=6, teeth=0))
    photo = build(xray_meta(bps=24, type=9, teeth=0), Image.new("RGB", (4, 4)))
    assert io.StudyInstanceUID == pan.StudyInstanceUID == photo.StudyInstanceUID
    assert (
        len({io.SeriesInstanceUID, pan.SeriesInstanceUID, photo.SeriesInstanceUID}) == 3
    )
    assert (io.SeriesNumber, pan.SeriesNumber, photo.SeriesNumber) == (1, 2, 3)


def test_a_new_edit_gets_a_new_instance_uid():
    plain = build(xray_meta(lux=(64, 64, 192, 192, 0, 0)))
    also_plain = build(
        xray_meta(lux=(72, 72, 200, 200, 0, 0))
    )  # another identity window
    edited = build(xray_meta(lux=(72, 61, 200, 255, 0, 0)))
    re_edited = build(xray_meta(lux=(72, 61, 210, 255, 0, 0)))
    assert plain.SOPInstanceUID == also_plain.SOPInstanceUID  # same pixels, same UID
    assert (
        len({plain.SOPInstanceUID, edited.SOPInstanceUID, re_edited.SOPInstanceUID})
        == 3
    )


def test_anonymized_patients_stay_apart():
    uids = dicom.UidMaker.anonymous()  # one salt for the whole run

    def anon(key):
        return dicom.dataset(
            Image.new("L", (4, 4)), xray_meta(), dicom.Identity(), uids, patient_key=key
        )

    a, b = anon("101"), anon("202")
    assert a.StudyInstanceUID != b.StudyInstanceUID
    assert a.SOPInstanceUID != b.SOPInstanceUID  # same file name, same day
    assert a.PatientID == b.PatientID == ""  # the key is hashed, never written
