# The .DEX file and the data root

## Container

Each `.DEX` is a little-endian TIFF (`49 49 2A 00`) with one page: an 8-bit grayscale preview at a quarter of the size (an x-ray of 1692x1324 carries a 424x332 preview; a 2016x1512 photo a 505x379 one). Compression 1 (none). Pillow and tifffile read the preview.

After the preview strip sits a block starting with the bytes `DEXIS!` holding the full-resolution image in DEXIS's own compression (`cmpr=2`). Its header has a 16-entry Huffman length table, so it is a custom lossless codec. There is no JPEG, PNG, or second TIFF IFD inside. dexport does not decode this block itself; `xfile.dll` does.

Large imported images (phone photos, outside-office mounts and pans up to 9316x4957) carry no `DEXIS!` block, and `XfileReadImg` decodes them all the same.

Private TIFF tags carry the metadata. Several hold patient identity, so read them only if you mean to:

| Tag  | Content                                             |
| ---- | --------------------------------------------------- |
| 1792 | patient ID                                          |
| 1793 | last name                                           |
| 1794 | first name                                          |
| 1795 | birthdate (MM/DD/YYYY)                              |
| 1810 | tooth series code (1846 = BW 18-46)                 |
| 1811 | image type: "IO (11 8 4)" x-ray, "IO" photo         |
| 1812 | capture "20260304 122225" (photo: "8/2/2023 10:51") |
| 1815 | practice or provider name                           |
| 1817 | device ("DEXIS Ti2#...", "IOC Snapshot")            |
| 2320 | offset of the full-res block                        |
| 2339 | full-res width                                      |
| 2340 | full-res height                                     |

Pictures (jpg, png, tif) never read the identity tags. DICOM output reads 1792 to 1795, because the software you import into needs the patient to file the image; `--anonymize` skips them. Date, teeth, type and rotation come through `xfile.dll`, which also normalises the two capture-date formats.

## Storage format setting

DEXIS Administration > Tools and Preferences > General > Format offers three storage formats: DEXIS (compressed, the default), uncompressed TIFF, and DICOM. The setting is per workstation, in `C:\DEXIS\Dexis.ini` `[SOFTWARE] cmpr=` (2 = DEXIS). Switching changes only new images.

## Data root and patient folders

`Dexis.ini`'s `xdata=` names the data root. A patient's folder is the patient ID zero-padded to five digits and split one digit per level: ID 12345 lives in `<root>\1\2\3\4\5\`.

Two fixed-width text indexes in that folder name the live images, one line each, path last:

- `DEXIS.dat` (the x-ray side): `YYYYMMDD  HHMMS ... series ... window ... 1\2\3\4\5\000017.DEX`
- `DEVIS.dat` (the photo side): `M/D/YYYY  HH:MM ... 1\2\3\4\5\p000004.DEX`

The indexes are the source of truth: a `.DEX` on disk that no index lists is not a live image. The window columns in `DEXIS.dat` are the same four saved-edit numbers as OriLux, and its x, y columns hold where staff dragged each image on screen.

## Current patient and lock files (the data-root top)

A few bookkeeping files live at the top of the data root (`<root>\`), not inside a patient folder. They let you read which patient DEXIS has open right now without the `DEXSRV32.DLL` session API:

| File             | Content                                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| `<HOSTNAME>.pat` | the patient ID open on that workstation, zero-padded, CRLF (`12345\r\n`)                                              |
| `DEXnet.lck`     | the hostname currently holding the DEXIS network lock (no newline)                                                    |
| `xpat.log`       | an append log of opened patient folder paths (`d\d\d\d\d\`), last = most recently written, not necessarily still open |
| `DEXIS.CHK`      | a zero-byte checkpoint flag                                                                                           |

DEXIS rewrites `<HOSTNAME>.pat` as the operator moves between patients, so it is the file-based equivalent of `DXL_GetCurrentPatient`: one file per workstation, named for the host. The ID is DEXIS's patient ID, the same number the patient folder is built from. `current.py` reads these (never writes); `dexport current` prints the patient open on this workstation, `--host NAME` another one, `--all` every workstation.

## What a real archive contains

From a stratified decode test over five years of one practice's images (a few hundred files picked across year, index side and size band; `dexport sweep` reproduces it on your own data):

- Every sampled file decoded. No failures.
- **The index side is not the image kind.** `DEXIS.dat` lists 24-bit phone photos, intraoral camera stills and video frames; `DEVIS.dat` lists 8-bit outside-office x-rays. The `p` filename prefix follows the index, so it inherits the same error. The bit depth is the honest classifier: 8-bit is an x-ray, 24-bit a photo (`XfileTryReadImageSize`'s `bps` is reliable even when its width and height are not).
- **The header over-reports.** `XfileTryReadImageSize` was exact on about 60% of files and 4 to 7 px larger than the decoded image on the rest. Trust the struct `XfileReadImg` returns.
- **Rotation codes 0 to 4 all occur.** 0 renders the same as 1 (no turn).
- **Acquisition time** is `HHMMSS`, `HHMM`, or empty (imported files). Undated files also carry rotation 0; fall back to the file's modification time for ordering.
- **About one x-ray in seven** carries a saved brightness and contrast edit.
- **Teeth = 0 is common** (imports, pans, and the photos that live on the x-ray side). It is not an error.
- **Sizes seen:** sensor x-rays 844x660 and 846x662 (older), 1692x1324 (Ti2), 1874x1402, 1200x1600, plus the odd scanned or stitched x-ray such as 2077x923; photos 640x480, 640x528, 2016x1512, 1920x1080, 1896x2532, and phone sizes up to 4032x3024. The large imported photos (1512x2016 and up) carry no `DEXIS!` block and decode the same.
- **Decode time over SMB:** 30 to 150 ms for a typical sensor x-ray, about 400 ms for a 2016x1512 photo, 1.5 s for the largest imports.
- `XfileReadNumberOfFrames` returned 1 for every file.
