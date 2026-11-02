# How DEXIS lays out a full-mouth series

DEXIS stores no mount template. Its manual says each image's "home" position comes from its tooth number, and `DEXIS.dat`'s x and y columns hold where staff dragged each image afterward.

The closest thing to a template in DEXIS.EXE is its film-scan layouts, stored as strings (9.5.3: near `0x51f4a5`, file offset `0x11f4a5`). Each is three rows of tooth codes with cut lines in percent of the width:

```
upper  1816 20 1614 35 1312 45 1121 55 2223 65 2426 80 2628
bw     1846 20 1644 42 1232 58 2436 80 2638
lower  4846 20 4644 35 4342 45 4131 55 3233 65 3436 80 3638
```

plus primary-dentition variants. Codes are FDI corner pairs (1816 is teeth 18 to 16). The patient's right sits on the viewer's left, as in a labial mount.

"Export FMX as one image" reads a `fmxexport` setting, `w h th rw fh`, defaulting to `2000 900 17 0 15` or `2100 1500 17 0 15` (read at `0x44fc19`): a canvas size and a 17 px title bar per image. The composition routine continues past `0x44fe9e` and has not been transcribed.

`Dexis.ini`'s `[PROGRAMS]` section holds the capture sequences; `series1` is the 18-film full-mouth series in FDI corner codes. The DEXIS install's `C:\DEXIS\Simulation\DXQ*.DEX` samples are a complete 18-film series, handy for testing a layout.

`dexport.mount.compose` follows these rows: each x-ray goes in the row its teeth belong to, centred over its place along the arch, with a title bar naming the teeth (Universal numbering) and the date. Images with no tooth code (pans, cephs, imports) go in a last row. The exact pixel positions are dexport's own.
