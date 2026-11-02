"""DICOM code values for intraoral anatomy, from PS3.16 (2026d).

Teeth are CID 4018 (permanent) and CID 4019 (deciduous), keyed here by their ISO 3950
(FDI) designation; the code itself is the SNOMED CT concept, scheme "SCT". Regions are
CID 4016. Generated from the standard's tables, not typed in; meanings are verbatim,
including CID 4018's "Mandibular left lateral tooth" for FDI 32.
"""

SCT = "SCT"

# CID 4016 Anatomic Region for Intra-oral Radiography. The standard has no
# "maxilla and mandible" (T-D1217 is deprecated); "Jaw region" covers both arches.
MAXILLA = ("70925003", SCT, "Maxilla")
MANDIBLE = ("91609006", SCT, "Mandible")
JAW_REGION = ("661005", SCT, "Jaw region")
TEETH_GUMS = ("28035005", SCT, "Teeth, gums and supporting structures")

# CID 4018 and CID 4019: FDI tooth -> (code value, code meaning)
TEETH: dict[int, tuple[str, str]] = {
    11: ("422653006", "Permanent maxillary right central incisor tooth"),
    12: ("424877001", "Permanent maxillary right lateral incisor tooth"),
    13: ("860767006", "Permanent maxillary right canine tooth"),
    14: ("57826002", "Permanent maxillary right first premolar tooth"),
    15: ("36492000", "Permanent maxillary right second premolar tooth"),
    16: ("865995000", "Permanent maxillary right first molar tooth"),
    17: ("863902006", "Permanent maxillary right second molar tooth"),
    18: ("68085002", "Permanent maxillary right third molar tooth"),
    21: ("424399000", "Permanent maxillary left central incisor tooth"),
    22: ("423185002", "Permanent maxillary left lateral incisor tooth"),
    23: ("860780009", "Permanent maxillary left canine tooth"),
    24: ("61897005", "Permanent maxillary left first premolar tooth"),
    25: ("23226009", "Permanent maxillary left second premolar tooth"),
    26: ("865988009", "Permanent maxillary left first molar tooth"),
    27: ("863901004", "Permanent maxillary left second molar tooth"),
    28: ("87704003", "Permanent maxillary left third molar tooth"),
    31: ("425106001", "Mandibular left central incisor tooth"),
    32: ("423331005", "Mandibular left lateral tooth"),
    33: ("860782001", "Mandibular left canine tooth"),
    34: ("2400006", "Mandibular left first premolar tooth"),
    35: ("24573005", "Mandibular left second premolar tooth"),
    36: ("866006002", "Mandibular left first molar tooth"),
    37: ("863898000", "Mandibular left second molar tooth"),
    38: ("74344005", "Mandibular left third molar tooth"),
    41: ("424575004", "Mandibular right central incisor tooth"),
    42: ("423937004", "Mandibular right lateral incisor tooth"),
    43: ("860785004", "Mandibular right canine tooth"),
    44: ("80140008", "Mandibular right first premolar tooth"),
    45: ("8873007", "Mandibular right second premolar tooth"),
    46: ("866005003", "Mandibular right first molar tooth"),
    47: ("863899008", "Mandibular right second molar tooth"),
    48: ("38994002", "Mandibular right third molar tooth"),
    51: ("88824007", "Deciduous maxillary right central incisor tooth"),
    52: ("65624003", "Deciduous maxillary right lateral incisor tooth"),
    53: ("30618001", "Deciduous maxillary right canine tooth"),
    54: ("17505006", "Deciduous maxillary right first molar tooth"),
    55: ("27855007", "Deciduous maxillary right second molar tooth"),
    61: ("51678005", "Deciduous maxillary left central incisor tooth"),
    62: ("43622005", "Deciduous maxillary left lateral incisor tooth"),
    63: ("73937000", "Deciduous maxillary left canine tooth"),
    64: ("45234009", "Deciduous maxillary left first molar tooth"),
    65: ("51943008", "Deciduous maxillary left second molar tooth"),
    71: ("89552004", "Deciduous mandibular left central incisor tooth"),
    72: ("14770005", "Deciduous mandibular left lateral incisor tooth"),
    73: ("43281008", "Deciduous mandibular left canine tooth"),
    74: ("38896004", "Deciduous mandibular left first molar tooth"),
    75: ("49330006", "Deciduous mandibular left second molar tooth"),
    81: ("67834006", "Deciduous mandibular right central incisor tooth"),
    82: ("22445006", "Deciduous mandibular right lateral incisor tooth"),
    83: ("6062009", "Deciduous mandibular right canine tooth"),
    84: ("58646007", "Deciduous mandibular right first molar tooth"),
    85: ("61868007", "Deciduous mandibular right second molar tooth"),
}
