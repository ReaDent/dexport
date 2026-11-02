# dexxdb.dll: the database layer

dexport does not use dexxdb. It is documented here because it is how DEXIS's own tools open a patient, because its export call is the oracle that pinned down the display chain ([display.md](display.md)), and because two of its calls write when you would expect them not to.

Everything below was run against a synthetic data root: a copied `Dexis.ini` with `xdata` and every other path pointed at a scratch folder, holding copies of a test patient's files. `C:\DEXIS` was compared before and after each run and never changed.

## The open chain

```c
int    XdbInit(const char *dllDir, const char *name, const char *code); // same registration pair as XfileInit
Xdb   *XdbOpen(const char *iniPath, int mode);         // the ini FILE, not its folder; mode 3
Xpat  *XpatOpen(Xdb *db, const char *patId, char *name, char *birth, int *i1, char *s3, char *s4, char *s5, int *state);
int    XpatListImageIdsInRange(Xpat *p, int lo, int hi, char *buf, int buflen); // tab-separated relative paths; 1, or the length needed
Ximg  *XimgOpen(Xpat *p, const char *imageId);
void   XimgGetDisplayInfo(Ximg *img, int *vis, int *x, int *y, int *ori);       // from the DEXIS.dat line
void   XimgGetBrightnessInfo(Ximg *img, int *a1, int *a2, int *b1, int *b2, int *, int *); // the OriLux window, then 0, 0
int    XimgTryExportFile(Ximg *img, const char *dest);  // format from the extension
void   XimgClose(Ximg *); void XpatClose(Xpat *); void XdbClose(Xdb *);
```

Notes:

- `XdbInit`'s first argument is the folder it loads `GEAR32PD.DLL`, `IGMED32s.dll` and `JPEG32.DLL` from (copies beside dexxdb.dll work). It writes `syserr.log` there.
- `XdbOpen` returns a handle even when the ini is missing, so check its log. Patient calls need mode 3; other modes log "xray room mode not implemented".
- `XpatOpen` on an existing patient returns `Last^First` and `YYYYMMDD` in its first two buffers, and 0 in `*state`.
- Image IDs are the relative paths (`1\2\3\4\5\000017.DEX`). X-rays and photos both list. Records with status 2 are skipped.
- A `.DEX` in the patient folder is not listed without an index line.
- The synthetic root must sit on NTFS. On a case-sensitive file system (a WSL path, for example) lookups miss and `XpatOpen` creates a new patient.
- `XimgGetContrast` is a stub that writes four zeros. `XimgGetBlackWhite` parses the same `{%d %d}` tag as `XfileTryReadBlackWhite`.
- `XimgTryExportFile` needs the imaging DLLs above. X-rays come out as the stored pixels rotated for display, with no ClearVu. An edited x-ray comes out as an 8-bit palette image whose palette is the exact edit curve. Photos come out through the photo routine in [display.md](display.md).

## Hazards

1. **`XpatOpen` creates unknown patients.** On an ID it doesn't know, it writes `<folder>\<id>.INF` (with name and birthdate lines), appends to `xpat.log` at the top of the data root, and sets `*state = 2`. Check the patient folder exists before calling it, and expect the log append even then.
2. **`XimgTryExportFile` to `.tif` or `.dcm` writes into the source image.** It stores a generated UID (`<patId>.<date>.<time>`, 20 bytes into an empty field near the end) back into the `.DEX`. `.jpg`, `.bmp` and `.png` exports, and every read call, leave the file byte-identical. Never export tif or dcm against real data.

Still unprobed: `XdbTryListRecentImages`, `XdbListPatientIds`, `XimgGetObjects` (annotations), `Ximg*InstanceUID` (DICOM UIDs).
