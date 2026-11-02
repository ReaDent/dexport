"""Write a .DEX as a DICOM file that other imaging software can import.

Intraoral x-rays (DEXIS type 5, 8-bit, with a sensor pixel pitch) become Digital
Intra-Oral X-Ray Image Storage, For Presentation: modality IO, imager pixel spacing in mm,
tooth and arch anatomy codes, laterality from the teeth. That is the class DEXIS's own
DICOM export writes, and the pixels match it bit for bit: the stored image, the saved
brightness/contrast edit baked in with DEXIS's curve, turned upright. No ClearVu
sharpening, which is a viewing filter the receiving software applies its own way.

Everything else (photos, scanned or imported x-rays, pans and cephs, which DEXIS tags only
as "from another system") becomes Secondary Capture: the pixels and the dates, with no
claim about the modality beyond photo or x-ray.

Patient identity comes from the .DEX's own tags (DEXIS writes name, ID and birthdate into
every file), because the receiving software needs it to file the image. Pass
``anonymize=True`` to leave it out. UIDs are derived from the patient and the file, so
exporting the same image twice gives the same UIDs and an importer can skip duplicates.

This module reads; the only file it writes is the DICOM output.
"""

from __future__ import annotations

import datetime as dt
import re
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from . import __version__
from . import dicom_codes as codes
from .clearvu import window_lut
from .teeth import teeth_fdi
from .tonecurve import edit_curve, photo_edit
from .xfile import ImageMeta, upright

IO_PRESENTATION = (
    "1.2.840.10008.5.1.4.1.1.1.3"  # Digital Intra-Oral X-Ray, For Presentation
)
SECONDARY_CAPTURE = "1.2.840.10008.5.1.4.1.1.7"

INTRAORAL_TYPE = 5
SERIES = {"IO": 1, "OT": 2, "XC": 3}  # series number per modality within a study

# Private TIFF tags DEXIS writes into every .DEX (see docs/format.md).
TAG_PATIENT_ID, TAG_LAST, TAG_FIRST, TAG_BIRTH = 1792, 1793, 1794, 1795
TAG_DEVICE = 1817


@dataclass(frozen=True)
class Identity:
    patient_id: str = ""
    name: str = ""  # DICOM person name, Last^First
    birth_date: str = ""  # YYYYMMDD

    @property
    def empty(self) -> bool:
        return not (self.patient_id or self.name or self.birth_date)


def read_identity(path: Path | str, patient_id: int | None = None) -> Identity:
    """Name, ID and birthdate from the .DEX's DEXIS tags.

    ``patient_id`` (the DEXIS ID the patient folder is named for) wins over the tag, which
    some files leave at 0.
    """
    tags = _tags(path)
    pid = patient_id if patient_id is not None else tags.get(TAG_PATIENT_ID)
    last, first = _text(tags.get(TAG_LAST)), _text(tags.get(TAG_FIRST))
    name = f"{last}^{first}" if first else last
    return Identity(
        patient_id=str(int(pid)) if pid else "",
        name=name,
        birth_date=_us_date(_text(tags.get(TAG_BIRTH))),
    )


def device_model(path: Path | str) -> str:
    """Sensor model from the device tag ("DEXIS Ti2#<serial>" -> "Ti2"), else ''."""
    dev = _text(_tags(path).get(TAG_DEVICE))
    m = re.match(r"DEXIS\s+([^#]+)#", dev, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def pixels(raw: Image.Image, meta: ImageMeta) -> Image.Image:
    """The image as DEXIS's DICOM export holds it: saved edit applied, turned upright.

    X-rays get the edit curve on the gray levels (bit-exact against DEXIS's export).
    Photos get DEXIS's photo rendering, which it applies to every photo it exports.
    """
    if raw.mode == "L" and len(meta.lux) >= 4:
        lut = window_lut(*meta.lux[:4])
        if lut:
            raw = raw.point(lut)
    elif raw.mode == "RGB" and len(meta.lux) >= 4:
        raw = photo_edit(raw, edit_curve(*meta.lux[:4]))
    return upright(raw, meta.rotation)


def is_intraoral(meta: ImageMeta) -> bool:
    return (
        meta.kind == "xray"
        and meta.type == INTRAORAL_TYPE
        and meta.pixel_spacing is not None
    )


class UidMaker:
    """Deterministic UIDs (2.25 form). With a salt, nothing links them to the patient."""

    def __init__(self, salt: str = ""):
        self.salt = salt

    @classmethod
    def anonymous(cls) -> UidMaker:
        return cls(secrets.token_hex(16))

    def __call__(self, *parts: object) -> str:
        # A name-based UUID as a 2.25 UID (PS3.5 B.2). pydicom's generate_uid ignores its
        # entropy sources when given no prefix, so it cannot be used for stable UIDs.
        key = "\x1f".join(["dexport", self.salt, *map(str, parts)])
        return f"2.25.{uuid.uuid5(uuid.NAMESPACE_URL, key).int}"


def dataset(
    im: Image.Image,
    meta: ImageMeta,
    identity: Identity,
    uids: UidMaker,
    *,
    model: str = "",
    file_date: dt.datetime | None = None,
    patient_key: str | None = None,
) -> Dataset:
    """A complete DICOM dataset for one image whose pixels are already final.

    ``identity`` may be empty (anonymized). ``file_date`` stands in for the capture time
    on files DEXIS left undated (imports), so the image still lands on a date.
    ``patient_key`` keeps patients apart in the UIDs when ``identity`` is empty; it is
    only hashed (salted when anonymizing), never written.
    """
    intraoral = im.mode == "L" and is_intraoral(meta)
    when = meta.captured or file_date
    date = when.strftime("%Y%m%d") if when else ""
    time = when.strftime("%H%M%S") if when else ""
    if patient_key is None:
        patient_key = identity.patient_id or identity.name + identity.birth_date
    modality = "IO" if intraoral else "XC" if im.mode == "RGB" else "OT"
    series_no = SERIES[modality]  # a series holds one modality and one SOP class
    # A saved edit changes the pixels, and new pixels need a new instance UID.
    edit = meta.lux[:4] if meta.edited else ()

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.SOPClassUID = IO_PRESENTATION if intraoral else SECONDARY_CAPTURE
    ds.SOPInstanceUID = uids("image", patient_key, meta.path.name, date, time, *edit)
    ds.StudyInstanceUID = uids("study", patient_key, date)
    ds.SeriesInstanceUID = uids("series", patient_key, date, series_no)

    # Patient
    ds.PatientName = identity.name
    ds.PatientID = identity.patient_id
    ds.PatientBirthDate = identity.birth_date
    ds.PatientSex = ""
    if identity.empty:
        ds.PatientIdentityRemoved = "YES"
        ds.DeidentificationMethod = (
            "dexport --anonymize: name, ID and birthdate omitted"
        )

    # Study, series, image
    ds.StudyDate = ds.SeriesDate = ds.ContentDate = date
    ds.StudyTime = ds.SeriesTime = ds.ContentTime = time
    ds.AccessionNumber = ""
    ds.ReferringPhysicianName = ""
    ds.StudyID = ""
    ds.SeriesNumber = series_no
    ds.InstanceNumber = _instance_number(meta.path)
    ds.Manufacturer = "DEXIS" if model else ""
    if model:
        ds.ManufacturerModelName = model
    ds.SoftwareVersions = f"dexport {__version__}"

    _image_pixel(ds, im)
    if intraoral:
        _intraoral(ds, meta)
    else:
        _secondary_capture(ds, im, meta)
    return ds


def write(ds: Dataset, dest: Path) -> None:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationVersionName = f"DEXPORT_{__version__}"[:16]
    ds.file_meta = meta
    dest.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(dest, enforce_file_format=True)


# -- modules ------------------------------------------------------------------------------


def _image_pixel(ds: Dataset, im: Image.Image) -> None:
    rgb = im.mode == "RGB"
    ds.SamplesPerPixel = 3 if rgb else 1
    ds.PhotometricInterpretation = "RGB" if rgb else "MONOCHROME2"
    if rgb:
        ds.PlanarConfiguration = 0
    ds.Rows, ds.Columns = im.height, im.width
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = im.tobytes()
    ds.BurnedInAnnotation = "NO"
    ds.LossyImageCompression = "00"


def _intraoral(ds: Dataset, meta: ImageMeta) -> None:
    # DX Image: value 3 must be present and empty (PS3.3 C.8.11.3.1.1).
    ds.ImageType = ["DERIVED" if meta.edited else "ORIGINAL", "PRIMARY", ""]
    ds.Modality = "IO"
    ds.PresentationIntentType = "FOR PRESENTATION"
    ds.PositionerType = "NONE"
    ds.DetectorType = "SCINTILLATOR"
    # Uncalibrated, so Pixel Spacing may be present only equal to Imager Pixel Spacing
    # (PS3.3 10.7.1.1); measuring tools in many viewers read only Pixel Spacing.
    ds.ImagerPixelSpacing = ds.PixelSpacing = _spacing_mm(meta)
    ds.PixelIntensityRelationship = "LIN"
    ds.PixelIntensityRelationshipSign = -1  # higher value = less beam = brighter bone
    # Enumerated as exactly "0" and "1"; an int or float can be written "0.0".
    ds.RescaleIntercept, ds.RescaleSlope, ds.RescaleType = "0", "1", "US"
    ds.WindowCenter, ds.WindowWidth = 128, 256  # identity: the edit is in the pixels
    ds.PresentationLUTShape = "IDENTITY"
    # Every film DEXIS shows upright is seen from the facial side, patient's right on the
    # viewer's left: rows run toward the patient's left, columns toward the feet.
    ds.PatientOrientation = ["L", "F"]
    ds.AcquisitionContextSequence = []
    teeth = teeth_fdi(meta.teeth)
    ds.ImageLaterality = _laterality(teeth)
    ds.AnatomicRegionSequence = [_code(*_region(teeth))]
    if teeth:
        ds.PrimaryAnatomicStructureSequence = [_code(*_tooth(t)) for t in teeth]


def _secondary_capture(ds: Dataset, im: Image.Image, meta: ImageMeta) -> None:
    ds.Modality = "XC" if im.mode == "RGB" else "OT"  # matches SERIES in dataset()
    ds.ConversionType = "DI"
    ds.PatientOrientation = ""
    if meta.edited:
        ds.ImageType = ["DERIVED", "PRIMARY"]
    if meta.pixel_spacing:
        ds.NominalScannedPixelSpacing = _spacing_mm(meta)


def _spacing_mm(meta: ImageMeta) -> list[str]:
    # DEXIS's export writes the DLL's (first, second) nanometre pair as [second, first]
    # mm, whatever the rotation; matched exactly so an import measures the same as DEXIS.
    assert meta.pixel_spacing
    first, second = meta.pixel_spacing
    return [_ds(second / 1e6), _ds(first / 1e6)]


def _ds(v: float) -> str:
    return f"{v:.6f}".rstrip("0").rstrip(".")


# -- anatomy ------------------------------------------------------------------------------


def _laterality(teeth: list[int]) -> str:
    # R, L or B only for intraoral (no U). B is "both, i.e. midline": a film across the
    # midline, or one DEXIS recorded no teeth for.
    sides = {"R" if t // 10 in (1, 4, 5, 8) else "L" for t in teeth}
    return sides.pop() if len(sides) == 1 else "B"


def _region(teeth: list[int]) -> tuple[str, str, str]:
    arches = {"upper" if t // 10 in (1, 2, 5, 6) else "lower" for t in teeth}
    if arches == {"upper"}:
        return codes.MAXILLA
    if arches == {"lower"}:
        return codes.MANDIBLE
    if arches:
        return codes.JAW_REGION
    # No teeth recorded. The standard then wants a tooth-region modifier (incisor,
    # canine, premolar, molar) that DEXIS does not store; this is the one place the
    # output knowingly falls short of the IOD.
    return codes.TEETH_GUMS


def _tooth(fdi: int) -> tuple[str, str, str]:
    value, meaning = codes.TEETH[fdi]
    return value, codes.SCT, meaning


def _code(value: str, scheme: str, meaning: str) -> Dataset:
    item = Dataset()
    item.CodeValue, item.CodingSchemeDesignator, item.CodeMeaning = (
        value,
        scheme,
        meaning,
    )
    return item


# -- helpers ------------------------------------------------------------------------------


def _tags(path: Path | str) -> dict:
    try:
        with Image.open(path) as im:
            return dict(im.tag_v2)  # type: ignore[attr-defined]
    except OSError:
        return {}


def _text(v: object) -> str:
    if isinstance(v, bytes):
        v = v.decode("latin-1")
    return str(v or "").split("\x00", 1)[0].strip()


def _us_date(s: str) -> str:
    try:
        return dt.datetime.strptime(s, "%m/%d/%Y").strftime("%Y%m%d")  # noqa: DTZ007 (a date)
    except ValueError:
        return ""


def _instance_number(path: Path) -> int:
    digits = re.sub(r"\D", "", path.stem)
    return int(digits) if digits else 1
