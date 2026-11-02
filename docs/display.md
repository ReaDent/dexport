# How DEXIS draws an image, bit-exact

`XfileReadImg` gives the stored pixels. What DEXIS shows on screen, and writes when you Export, is those pixels after a processing chain. dexport reproduces the chain exactly: compressed with DEXIS's own JPEG tables, its output matches DEXIS's export with zero pixel difference.

## X-rays

```
raw decode -> ClearVuFilter.dll guided filter -> 3x3 median -> saved edit curve -> rotate
```

### ClearVu

`Dexis.ini` `clearvumode=2` is passed straight to DEXIS.EXE's ClearVu dispatcher: mode 2 loads `ClearVuFilter.dll` ("ClearVu 2.0 using guided filter", a wrapper around OpenCV `cv::ximgproc::guidedFilter`). Modes 1 and 3 take a different built-in path. `xfilter.dll`'s `XfilterClearVu*` functions are older algorithms; none of them match.

```c
void BetaFilterInit(void *block);              // ret 4: fills preset names and defaults
void BetaFilter(void *block, void *img);       // ret 8: filters img pixels in place
```

`img` is the struct `xfile.dll` returns and must be 8 bits per pixel (anything else pops a `MessageBoxA`, which hangs a headless process). `block` is a zeroed 0xD64-byte settings block that DEXIS.EXE fills like this:

| Offset                                   | Value               | Meaning                                                 |
| ---------------------------------------- | ------------------- | ------------------------------------------------------- |
| 0x000                                    | `"DEXIS9 Software"` | host name                                               |
| (call)                                   | `BetaFilterInit`    |                                                         |
| 0x590, 0x5D4, 0x618, 0x65C, 0x6A0, 0x6E4 | -1 each             | all six built-in presets off, so the numbers below rule |
| 0xB2C..0xB3C                             | 2, 0, 0, 255, 255   | not read by the filter                                  |
| 0xD50                                    | 0                   | not used when 0xD58 is set                              |
| 0xD58                                    | 15                  | window size (guided-filter radius 7)                    |
| 0xD5C                                    | 200                 | strength 2.00                                           |
| 0xD60                                    | 100                 | eps 0.0100                                              |

The values are the same for every image size. `ClearVuFilter.dll` must load from a folder that holds the 32-bit `opencv_core453.dll` and `opencv_ximgproc453.dll`, and needs the VC++ 2015+ x86 runtime; every DEXIS PC has both. No registration is involved.

### Median

After the filter, DEXIS.EXE runs its filter code `'M'` with window 3, a 3x3 median, on images whose sides are both under 2000 px. Pillow's `ImageFilter.MedianFilter(3)` matches it exactly, borders included.

Measured against DEXIS's own JPEG exports of unedited x-rays: the raw decode differs by about 2.7 gray levels and looks about 1.5 times sharper; after ClearVu and the median the difference is 0.7 to 0.9, all of it JPEG noise. Compressed with the export's own quantisation tables, every pixel is identical. About 0.3 s for the filter and 0.2 s for the median on a 1692x1324 image.

Whether DEXIS applies ClearVu on export depends on `expclearvu=yes` in that PC's `Dexis.ini`.

### The saved edit curve

When staff adjust brightness and contrast, DEXIS saves four numbers, the OriLux window `a1, a2, b1, b2` (also the window columns of `DEXIS.dat`). The curve is built by dexxdb.dll at `0x449b7c(a1, a2, b1, b2)`, and DEXIS.EXE's display uses the same curve.

Construction (all integer, following the x86 code):

1. Q1 and Q2 are the quarter points of the segment (a1, a2)-(b1, b2), by integer halving.
2. A quadratic Bezier from (0, 0) with control (a1, a2) to Q1 (`0x449990`).
3. A straight line Q1 to Q2 (`0x449084`, unsigned floor division, clamped to 0..255).
4. A quadratic Bezier from Q2 with control (b1, b2) to (255, 255) (`0x4497c8`).
5. If a2 > b2 the ends flip to (0, 255) and (255, 0).

Each Bezier is stepped in 16.16 fixed point (`0x4496b8`, keeps the low byte). `0x449694` compares the end slopes and, for the other curvature, reruns the segment on swapped axes into a temp table merged back by `0x449730`. Multiplies wrap at 32 bits and `idiv` truncates toward zero.

`tonecurve.edit_curve` is the Python transcription. It matches all 233 palettes DEXIS wrote for it, including decreasing, crossed, equal and extreme windows (60 of them are the test data). Models that were tried first and rejected: cubic Bezier (max error 44), quadratic B-spline (39), a fitted toe and shoulder (64).

**The no-edit rule:** the curve is the identity exactly when `a1 == a2`, `b1 == b2` and `a1 <= b1`. A crossed equal window such as (200, 200, 10, 10) is a real curve, and DEXIS draws it.

How the curve was pinned down: `XimgTryExportFile` writes an edited x-ray as an 8-bit palette BMP, and the palette is the curve. Rewriting the window columns of one line in a scratch copy of `DEXIS.dat` and exporting again gives a palette for any window you like.

### Rotation

Rotation commutes with everything above, so it goes last. OriLux codes: 0 and 1 no turn, 2 = 270, 3 = 180, 4 = 90.

## Photos

Photos skip ClearVu. DEXIS's export runs every photo, edited or not, through a hand-written 16-bit routine at dexxdb `0x442d74(row, width, T76, T151, T29, lut, hue=0, sat=0x100)`, called per row from `0x44956c`. The tables come from `0x449310`: `T_k(v) = k * (v & 0xFE)`. `lut` is the edit curve above (identity when unedited).

Per pixel (BGR in memory):

```
Y  = (T76[R] + T151[G] + T29[B]) >> 8
R' = clamp(R - Y + L[Y])
B' = clamp(B - Y + L[Y])
G' = clamp(trunc(((L[Y] << 8) - T29[B'] - T76[R']) / 151))
```

So the curve acts on luma, red and blue keep their offset from Y, and green is solved back. Because it runs on every photo, an unedited export differs from the raw decode only in green, by 1 to 3 levels. The hue and saturation path was zero on every image seen.

`tonecurve.photo_edit` reproduces it; the output equals DEXIS's BMP export byte for byte.
