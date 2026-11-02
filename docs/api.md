# DEXIS DLL API, as verified

Everything here was recovered from the disassembly of DEXIS 9.5.3 binaries and then confirmed by calling it. "Verified" means it ran and returned the expected data on real files. "Bound, unverified" means the argument count matches the stack cleanup (`ret N`) but the meaning of an argument is a guess.

All exports are `__stdcall` with ANSI C strings. Every DLL is 32-bit x86.

## xfile.dll (the one that matters)

Imports only KERNEL32, USER32, MPR, SHELL32. Runs from a copy; does not need DEXIS.EXE, `Dexis.ini`, or an open patient database.

```c
int   XfileInit(const char *logDir, const char *name, const char *code);  // returns 1; a wrong pair still returns 1 but every read then NULLs
void *XfileReadImg(const char *path);                                      // NULL on failure; FAULTS on a missing path, check first
void *XfileReadImgFrame(const char *path, int frame);                     // multi-frame files
int   XfileReadNumberOfFrames(const char *path);                          // 1 on every file sampled so far
void  XfileFreeImg(void *img);                                            // frees pixels and struct
int   XfileTryReadImageSize(const char *path, int *w, int *h, int *bps);  // w/h over-report by 0 to 7 px; bps (8 or 24) is reliable
int   XfileTryReadTypeAndTeeth(const char *path, int *type, int *teeth);
int   XfileTryReadAcquisitionDateTime(const char *path, char *date, char *time); // date YYYYMMDD; time HHMM, HHMMSS, or ""
int   XfileTryReadOriLux(const char *path, int *rot, int *a1, int *a2, int *b1, int *b2, int *v5, int *v6);
int   XfileTryReadPixelSpacing(const char *path, int *pixw, int *pixh);   // pixel pitch in nanometres; 0/absent on non-sensor images
int   XfileTryReadOrientation(const char *path, int *, int *, int *);     // values not decoded
void *XfileReadThumbnail(const char *path, int maxSize, int *scale);      // same struct as XfileReadImg; free with XfileFreeImg
int   XfileCheckCrc(const char *path);                                    // 0 intact, 1 CRC mismatch, -1 unreadable
int   XfileTryReadBlackWhite(const char *path, int *black, int *white);   // bound, unverified: no sample carries the tag
```

`XfileInit`'s first argument is a folder it probes for a logging DLL; point it at an empty temp folder and it writes nothing. The name and code are the registration pair (see [REGISTRATION.md](../REGISTRATION.md)).

`XfileReadThumbnail` picks the largest divisor of 1, 2, or 4 that keeps the long side at or above `maxSize` and writes it to `*scale`; at divisor 1 the pixels match `XfileReadImg` exactly. On a 792x632 x-ray: 64 gives 198x158 (4), 256 gives 396x316 (2), 1000 gives the full image.

`XfileCheckCrc` covers only part of the file: a flipped byte near the start returns 1, flips deep in the pixel data return 0.

`XfileTryReadBlackWhite` parses a `{%d %d}` tag; it returns 0 and leaves both outputs untouched when the tag is absent (all 48 Simulation samples).

Success returns are set with `or al, 1`, so test for nonzero, not `== 1`.

Returned image struct (read from the live pointer, 24 bytes):

```c
struct { int32 width; int32 height; int32 bitsPerPixel; int32 unused; int32 stride; uint8 *pixels; }
```

Pixels are top-down. 24-bit is BGR; 8-bit is one byte per pixel. `XfileReadImg16` returned NULL on every file tried (x-rays are stored 8-bit).

OriLux: `rot` is 0 or 1 for no turn, 2 = 270, 3 = 180, 4 = 90 (Pillow `transpose` constants, mapped from a full-mouth series). `a1, a2, b1, b2` are the saved display window; `a1 == a2 && b1 == b2` (with `a1 <= b1`) means no edit. See [display.md](display.md).

Type codes: 5 intraoral x-ray, 6 x-ray from another system, 9 IOC Snapshot photo, 10 imported file or video frame. Teeth: an int built from FDI numbers, 0 none, `36` one tooth, `1846` two corner teeth (see `teeth.py`).

Pixel spacing: `XfileTryReadPixelSpacing` gives the sensor pixel pitch in nanometres, the same value for width and height. Measured 19500 on the 1692x1324 sensor (19.5 um, the DEXIS Platinum/Ti pitch) and 39000 to 40280 on the 844x660 and 846x662 older sensors. Photos, imported images and scanned x-rays carry none. Verified across 179 files of three patients (2024 to 2026), 0 decode failures.

Exports present but not bound (read side, candidates): `XfileReadNotes`, `XfileTryReadCrownPos`, `XfileTryReadExposureValues`, `XfileTryReadDeviceValues`, `XfileTryReadPatientInfo[Ex]` (patient name and birthdate; deliberately not bound), `XfileIsDicomFile`, `XfileReadImgFromBuffer`.

Write exports, never bound: `XfileWrite`, `XfileUpdate*`, `XfileSet*`, `XfileMake*`, `XfileAddDicomDir`. `tests/test_no_writes.py` fails if any of them, or the dexxdb write calls, appear in the source.

## ClearVuFilter.dll

Needs the `opencv_*453.dll` files beside it (load from `C:\DEXIS` with `os.add_dll_directory`). Wraps `cv::ximgproc::guidedFilter`.

```c
void BetaFilterInit(void *block);        // fills preset names and defaults into a 0xD64-byte block
void BetaFilter(void *block, void *img); // filters the 8-bit pixels of an xfile image struct in place
```

The settings block DEXIS.EXE builds, and the median that follows, are in [display.md](display.md).

## dexxdb.dll (the database layer; not used by dexport)

Covered in [dexxdb.md](dexxdb.md), including two calls that write when you would expect them not to.

## Dexacc32.dll (the official third-party surface; not used)

`OpenDexisDatabase[Ex]`, `OpenDexisPatient[Ex]`, `ReadDexisFile[Ex]`, `TryGetDexisPatientInfo`, `TestDexisComponentRegistered`, `TryRegisterDexisImageSource`, plus write calls (`AddDexisImage*`, `WriteDexisFile`). `DEXBONE.EXE` and `Dexbild.dll` link against it.

## DEXSRV32.DLL (not used)

`DXL_Open`, `DXL_GetCurrentPatient`, `DXL_GetPatientList`, `DXL_GetPatientData`, `DXL_Close`: which patient is open in DEXIS right now. dexport does not load this DLL; `current.py` reads the same current-patient signal from the `<HOSTNAME>.pat` file at the data-root top instead (see [format.md](format.md)).

## Everything else in C:\DEXIS

Sensor acquisition (`DEXlib`, `DEXcard`, `Polaris`, `NimfDriver`, `FSErgo`, `FusionLib`, `CMOSDentalCamera`, `DIOSAcqLib`, `DEXusbManager`, `DBUSB`), camera capture (`Video32`, `Acclaim`, `BDADLL`), raw correction (`Dexbild`, `Xbild`), DICOM (`DEXcom` C-STORE/FIND/MOVE client, stock DCMTK `dcm*.dll`, Accusoft `IGMED32s`/`GEAR32PD`), `xfilter.dll` (sharpen, emboss, 16-to-8, older ClearVu algorithms that do not match DEXIS's current output), `JPEG32.DLL`, spell check, logging, OpenCV 4.5.3. The EXEs are GUI tools (`dexcopy.exe` exports whole patients to uncompressed TIFF or DICOM, no command-line switches found). `.MCS` files are sensor FPGA firmware (Intel HEX). `DManUS.pdf` is the DEXIS 9 manual.
