# DICOM export

`dexport export PATIENT_ID --fmt dcm --to DIR` (or `decode FILE.DEX --fmt dcm`) writes one DICOM file per image, Explicit VR Little Endian, uncompressed. It is meant for moving images into other imaging software, which imports DICOM as x-rays with the patient, date, teeth and scale attached; a JPEG arrives as a picture.

## Which DICOM object each image becomes

| Image                                                                                        | SOP class                                                                        | Modality |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------- |
| Intraoral x-ray: DEXIS type 5, 8-bit, with a sensor pixel pitch                              | Digital Intra-Oral X-Ray Image, For Presentation (`1.2.840.10008.5.1.4.1.1.1.3`) | IO       |
| Any other x-ray: pans, cephs, scans and imports ("from another system", type 6), or no pitch | Secondary Capture (`1.2.840.10008.5.1.4.1.1.7`)                                  | OT       |
| Photo (24-bit)                                                                               | Secondary Capture, RGB                                                           | XC       |

DEXIS does not record whether a type 6 image is a pan, a ceph or a scanned film, so dexport does not claim one; those keep their pixel pitch as Nominal Scanned Pixel Spacing when DEXIS has it.

## Matching DEXIS's own export

The intraoral object is the one DEXIS's DICOM export writes. dexport was checked against DEXIS's export of seven x-rays from two sensor generations (one with a saved brightness/contrast edit), field by field: SOP class, pixels (byte-identical), rows and columns, imager pixel spacing, laterality, the teeth, patient name, ID and birthdate, study date, patient orientation, window, sensor model, and which images share a study. All matched. What the two have in common:

- **Pixels:** the stored image, the saved edit applied with DEXIS's tone curve (see [display.md](display.md)), turned upright. No ClearVu sharpening; that is a viewing filter the receiving software applies its own way. An edited image is `DERIVED\PRIMARY\`, an unedited one `ORIGINAL\PRIMARY\`.
- **Window:** center 128, width 256, the identity for 8-bit, because the edit is already in the pixels.
- **Spacing:** `XfileTryReadPixelSpacing`'s nanometre pair (first, second) is written as `[second, first]` mm, whatever the rotation, exactly as DEXIS writes it. dexport also writes Pixel Spacing equal to it (the standard allows that for an uncalibrated image) because some viewers' measuring tools read only Pixel Spacing.
- **Teeth:** every tooth the film covers, not just DEXIS's two corner teeth (a right molar bitewing is 16 17 18 46 47 48), as SNOMED CT codes from CID 4018 (permanent) and CID 4019 (deciduous).
- **Region and laterality:** Maxilla, Mandible, or both arches; R, L, or B for a film across the midline.
- **Orientation:** `L\F`. DEXIS shows every film from the facial side with the patient's right on the viewer's left, so rows run toward the patient's left and columns toward the feet.
- **Grouping:** one study per patient per capture date. Within it, one series per kind of object (intraoral x-rays 1, other x-rays 2, photos 3), because a series holds a single modality.

Where dexport differs on purpose:

- **Both arches** is `661005` "Jaw region". DEXIS writes the old SNOMED-RT "Maxilla and mandible", which the standard has deprecated with no replacement. All codes use the current `SCT` scheme rather than DEXIS's retired `SNM3`.
- **Left out:** the practice name, workstation name, sensor serial number, and DEXIS's private tags. dexport writes the sensor model (Ti2, Platinum) and "DEXIS" as the manufacturer.
- **Times** are written as valid `HHMMSS`. DEXIS writes nine digits there, which validators reject.

## Standards check

Output was validated with [dicom-validator](https://github.com/pydicom/dicom-validator) against DICOM 2026d: the intraoral object (bitewing, single tooth, edited, anonymized), a pan and a photo as Secondary Capture all pass with no errors. DEXIS's own export, run through the same check, fails on the time format and two attributes the IOD does not define.

The one case that does not fully pass: an intraoral film DEXIS recorded no teeth for. The standard then wants a tooth-region modifier (incisor, canine, premolar or molar region), which DEXIS does not store. dexport still writes it as an intraoral x-ray, with region "Teeth, gums and supporting structures" and laterality B, because the software you import into files by modality and a generic Secondary Capture would lose more than that one code.

## Patient identity

The patient name, ID and birthdate come from DEXIS's own tags in each `.DEX` (see [format.md](format.md)); `export` uses the patient ID you gave it. Sex is left empty: DEXIS keeps it outside the image file.

`--anonymize` leaves out name, ID and birthdate, sets Patient Identity Removed, and salts the UIDs so they cannot be recomputed from a guessed patient ID. Capture dates are kept. It is meant for teaching sets, not for a formal de-identification.

## UIDs

UIDs are name-based UUIDs in the `2.25.` form, derived from the patient, the file, the date and any saved edit. Export the same image twice and it gets the same UIDs, so an importer that already has it can skip it; change its brightness or contrast in DEXIS and the next export is a new instance, because its pixels changed. Anonymized exports are salted per run, and still keep patients apart.

## Not covered

- No `DICOMDIR`. Most software imports a folder of `.dcm` files; a DICOMDIR is only needed for CD/DVD media.
- No multi-frame output (no multi-frame `.DEX` has turned up).
- No DICOM network send (C-STORE); write files and import them.

dexport never uses dexxdb's `XimgTryExportFile` for DICOM: its `.dcm` export writes a UID back into the source `.DEX` (see [dexxdb.md](dexxdb.md)). Everything here reads the `.DEX`; the only file written is the output.
