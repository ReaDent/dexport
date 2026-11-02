# dexport

Read and export your own DEXIS 9 x-rays and photos, through DEXIS's own DLLs. No DEXIS window, no clicking through Export one image at a time.

- Decodes `.DEX` files to full resolution (8-bit x-rays, 24-bit photos).
- Reads each image's metadata without decoding it: capture date and time, teeth, image type, rotation, saved brightness and contrast edit.
- Reproduces what DEXIS shows on screen, bit for bit: the ClearVu filter, the 3x3 median, the saved edit curve and rotation for x-rays, and DEXIS's own color rendering for photos.
- Lists a patient's live images from the DEXIS index files.
- Lays x-rays out as a full-mouth mount (upper periapicals, bitewings, lower periapicals) with a title bar per film.

It is read-only toward DEXIS. It binds no DEXIS export that writes, and a test fails if one is ever added.

Not affiliated with or endorsed by DEXIS or its owners. DEXIS is their trademark.

## What you need

- A Windows PC with DEXIS 9 installed in `C:\DEXIS` (verified against 9.5.3), signed in as someone who can open your DEXIS images. Any workstation that runs DEXIS will do. dexport uses DEXIS's own DLLs from that install; none are included here.
- The DEXIS registration pair your licensed install uses (see step 3).
- About 10 minutes. No administrator rights, and you don't need Python or git already installed.

## Setup

Run each step in PowerShell (Start menu, type `powershell`, open **Windows PowerShell**).

**1. Install uv**, the tool that fetches the right Python and installs dexport:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close PowerShell and open a new window so it picks up `uv`.

**2. Install dexport.** Every DEXIS DLL is 32-bit, so this asks uv for a 32-bit Python; uv downloads it the first time.

```powershell
uv tool install --python cpython-3.12-windows-x86 "dexport @ https://github.com/ReaDent/dexport/archive/refs/heads/main.zip"
```

If the next step says `dexport` is not recognized, run `uv tool update-shell` and open a new window.

**3. Add your registration pair.** `xfile.dll` decodes nothing without the name and code your DEXIS install is registered with. Put them on one line as `NAME:CODE`:

```powershell
mkdir "$env:APPDATA\dexport" -Force
Set-Content "$env:APPDATA\dexport\registration.txt" "NAME:CODE"
```

[REGISTRATION.md](REGISTRATION.md) has the other ways to supply it, including one file shared by every PC in an office.

**4. Check everything:**

```powershell
dexport doctor
```

A working setup looks like this:

```
arch_ok                True
xfile.dll              True
ClearVuFilter.dll      True
registration           configured
XfileInit              1
sample_decode          L 792x632
data_root              D:\DexisData
data_root_reachable    True
```

`sample_decode` decodes one of the practice-free sample images DEXIS installs in `C:\DEXIS\Simulation`, which is the only real proof the registration pair is right. `data_root` is where your DEXIS keeps patient images, read from `xdata=` in `C:\DEXIS\Dexis.ini`.

**5. Export a patient's images.** Use the patient ID DEXIS shows for that patient:

```powershell
dexport list 12345
dexport export 12345 --to "$env:USERPROFILE\Desktop\dexis-12345"
```

That writes each image as a JPEG that looks the way DEXIS shows it on screen, named after its DEXIS file. Add `--kind xray` or `--kind photo` for one kind, or `--since-days 365` for the last year.

## Updating and removing

```powershell
uv tool install --reinstall --python cpython-3.12-windows-x86 "dexport @ https://github.com/ReaDent/dexport/archive/refs/heads/main.zip"
uv tool uninstall dexport
```

Your registration file stays in `%APPDATA%\dexport` either way.

## Troubleshooting

| `dexport doctor` shows                      | What it means                                                                   | Fix                                                                     |
| ------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `arch_ok False`                             | dexport is running under 64-bit Python                                          | Reinstall with `--python cpython-3.12-windows-x86` exactly as in step 2 |
| `xfile.dll False`                           | DEXIS isn't in `C:\DEXIS`                                                       | Add `--dexis-dir "D:\Path\To\DEXIS"` to every command                   |
| `registration MISSING`                      | No pair found                                                                   | Step 3; the line names the file it looked for                           |
| `sample_decode FAILED`                      | The pair is wrong (DEXIS accepts any pair at startup, then refuses every image) | Check the name and code; they are case-sensitive                        |
| `data_root unknown`                         | `Dexis.ini` has no `xdata=` line                                                | Set `DEXIS_DATA_ROOT` to your image folder, or pass `--dexis-root`      |
| `data_root_reachable no (Access is denied)` | Windows won't let this account read the DEXIS share                             | Run as a user who can open the images in DEXIS, or map the share first  |
| `no DEXIS folder for patient N`             | No images under that ID                                                         | Check the ID DEXIS shows for the patient                                |

Problems and questions go in [Issues](https://github.com/ReaDent/dexport/issues). Never attach patient images or anything with a patient's name, ID or birthdate.

## Commands

```
dexport doctor                                    arch, DLLs, registration, data root
dexport info   FILE.DEX [--json]                  metadata without decoding
dexport decode FILE.DEX [out.jpg] [--raw] [--fmt jpg|png|tif]
dexport list   PATIENT_ID [--json]                a patient's live images
dexport export PATIENT_ID --to DIR [--kind xray|photo] [--since-days N] [--raw]
dexport sweep  listing.tsv OUT [--per-cell N]     stratified decode test (path<TAB>date<TAB>size)
```

`decode` and `export` match what DEXIS shows by default; `--raw` gives the stored pixels, upright. The data root comes from `--dexis-root`, else `DEXIS_DATA_ROOT`, else `xdata=` in `C:\DEXIS\Dexis.ini`.

As a library:

```python
from dexport.export import Exporter
ex = Exporter()                        # loads xfile.dll and ClearVuFilter.dll once
im, meta, ms = ex.render(r"D:\DexisData\1\2\3\4\5\000022.DEX")   # Pillow image, ImageMeta, decode ms

from dexport.catalog import DexisRoot
for f in DexisRoot().images(12345):    # every image the patient's indexes list
    print(f.path.name, ex.xf.meta(f.path).captured)
```

## How it works

The [docs](docs/) are the breakdown: how a `.DEX` file is built, every DLL export that was recovered and verified, how DEXIS draws an x-ray and a photo, the database DLL and its hazards, and the mount layout.

- [docs/format.md](docs/format.md): the `.DEX` container, the index files, what a real archive contains
- [docs/api.md](docs/api.md): `xfile.dll`, `ClearVuFilter.dll`, `dexxdb.dll` and the others, signature by signature
- [docs/display.md](docs/display.md): the ClearVu chain, the edit curve, the photo path, all bit-exact
- [docs/dexxdb.md](docs/dexxdb.md): the database DLL's open chain, and two ways it writes when you'd expect it not to
- [docs/mount.md](docs/mount.md): how DEXIS lays out a full-mouth series
- [docs/reversing.md](docs/reversing.md): notes on the binaries' calling convention, for anyone going further

## Development and tests

```powershell
git clone https://github.com/ReaDent/dexport
cd dexport
uv run --python cpython-3.12-windows-x86 pytest
```

The pure-Python tests (tooth codes, the edit curve, the photo rendering, the mount layout, the catalog) run anywhere. The DLL tests use the sample images in `C:\DEXIS\Simulation` and skip when DEXIS, those samples, or a registration pair is missing.

## Contributing

Issues and pull requests are welcome, especially results from other DEXIS versions and sensors. Never attach patient images or anything with a patient's name, ID or birthdate; the Simulation samples are enough to show almost any problem.
