"""The ``dexport`` command. Every verb prints a short text report; ``--json`` gives the data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

from . import VERIFIED_DEXIS_VERSION, __version__, arch_ok
from .catalog import DexisRoot, default_root
from .registration import RegistrationMissing, config_file, configured

ARCH_MSG = "dexport needs 32-bit Windows Python: uv run --python cpython-3.12-windows-x86 dexport ..."


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(
        prog="dexport", description="Read and export your own DEXIS 9 images"
    )
    ap.add_argument(
        "--dexis-dir", type=Path, default=None, help=r"DEXIS install folder (C:\DEXIS)"
    )
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check arch, DLLs, registration, data root")
    p = sub.add_parser("info", help="metadata of one .DEX")
    p.add_argument("dex", type=Path)
    p = sub.add_parser("decode", help="one .DEX to an image file")
    p.add_argument("dex", type=Path)
    p.add_argument("out", type=Path, nargs="?")
    p.add_argument("--raw", action="store_true", help="skip the ClearVu display chain")
    p.add_argument("--fmt", choices=["jpg", "png", "tif"], default="jpg")
    p = sub.add_parser("list", help="a patient's live images")
    p.add_argument("patient_id", type=int, help="DEXIS patient ID")
    p.add_argument("--dexis-root", type=Path, default=None)
    p = sub.add_parser("export", help="a patient's images to a folder")
    p.add_argument("patient_id", type=int, help="DEXIS patient ID")
    p.add_argument("--to", type=Path, required=True)
    p.add_argument("--kind", choices=["xray", "photo"])
    p.add_argument("--since-days", type=int)
    p.add_argument("--fmt", choices=["jpg", "png", "tif"], default="jpg")
    p.add_argument("--raw", action="store_true")
    p.add_argument("--dexis-root", type=Path, default=None)
    p = sub.add_parser(
        "current", help="which patient DEXIS has open now (reads <root>\\<host>.pat)"
    )
    p.add_argument("--host", default=None, help="another workstation's name")
    p.add_argument(
        "--all", action="store_true", help="every workstation with a patient open"
    )
    p.add_argument("--dexis-root", type=Path, default=None)
    p = sub.add_parser(
        "sweep", help="stratified decode test over a listing (path<TAB>date<TAB>size)"
    )
    p.add_argument("listing", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--per-cell", type=int, default=4)
    p.add_argument("--seed", type=int, default=20261006)
    a = ap.parse_args(argv)

    if a.cmd == "doctor":
        return doctor(a)
    if a.cmd == "current":  # pure file reads, no DLLs or registration needed
        try:
            return current(a)
        except FileNotFoundError as e:
            sys.exit(str(e))
    if not arch_ok():
        sys.exit(ARCH_MSG)
    try:
        run(a)
    except (RegistrationMissing, FileNotFoundError) as e:
        sys.exit(str(e))


def run(a) -> None:
    kw = {"dexis_dir": a.dexis_dir} if a.dexis_dir else {}

    if a.cmd == "info":
        from .xfile import Xfile

        m = Xfile(**kw).meta(a.dex)
        print(json.dumps(m.as_dict(), indent=1) if a.json else fmt_meta(m))

    elif a.cmd == "decode":
        from .export import Exporter

        out = a.out or a.dex.with_suffix("." + a.fmt)
        r = Exporter(display=not a.raw, **kw).export(a.dex, out, a.fmt, sidecar=a.json)
        print(
            f"{r.source.name}: {r.mode} {r.width}x{r.height} decode={r.decode_ms}ms -> {r.dest}"
        )

    elif a.cmd == "list":
        root = DexisRoot(a.dexis_root) if a.dexis_root else DexisRoot()
        from .xfile import Xfile

        xf = Xfile(**kw)
        rows = []
        for f in root.images(a.patient_id):
            m = xf.meta(f.path)
            rows.append({"file": f.path.name, "index": f.source, **m.as_dict()})
        if a.json:
            print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                print(
                    f"{r['file']:<12} {r['kind']:<5} {r['captured'] or '?':<19} {r['header_width']}x{r['header_height']} type={r['type']} teeth={r['teeth']} rot={r['rotation']}"
                )

    elif a.cmd == "export":
        import datetime as dt

        from .export import Exporter

        root = DexisRoot(a.dexis_root) if a.dexis_root else DexisRoot()
        ex = Exporter(display=not a.raw, **kw)
        cutoff = (
            dt.datetime.now() - dt.timedelta(days=a.since_days)
            if a.since_days
            else None
        )
        n = 0
        for f in root.images(a.patient_id):
            m = ex.xf.meta(f.path)
            if a.kind and m.kind != a.kind:
                continue
            if cutoff and (m.captured or dt.datetime.fromtimestamp(f.mtime)) < cutoff:
                continue
            r = ex.export(f.path, a.to / f"{f.path.stem}.{a.fmt}", a.fmt)
            print(
                f"{r.source.name}: {r.mode} {r.width}x{r.height} {r.decode_ms}ms -> {r.dest.name}"
            )
            n += 1
        print(f"{n} exported to {a.to}")

    elif a.cmd == "sweep":
        sweep(a.listing, a.out, a.per_cell, a.seed, kw)


def fmt_meta(m) -> str:
    d = m.as_dict()
    return "\n".join(f"{k:<14} {v}" for k, v in d.items())


def doctor(a) -> None:
    import ctypes
    import platform

    dexis_dir = a.dexis_dir or Path(r"C:\DEXIS")
    report = {
        "dexport": __version__,
        "python": f"{platform.python_version()} {platform.architecture()[0]} {sys.platform}",
        "arch_ok": arch_ok(),
        "dexis_dir": str(dexis_dir),
        "verified_against": VERIFIED_DEXIS_VERSION,
    }
    for name in (
        "xfile.dll",
        "ClearVuFilter.dll",
        "opencv_core453.dll",
        "opencv_ximgproc453.dll",
    ):
        report[name] = (dexis_dir / name).exists()
    report["registration"] = (
        "configured"
        if configured()
        else f"MISSING (see REGISTRATION.md; file {config_file()})"
    )
    if report["arch_ok"] and report["xfile.dll"] and configured():
        try:
            from .xfile import Xfile

            xf = Xfile(dexis_dir)
            report["XfileInit"] = xf.init_rc
            # A wrong pair still initialises; only a decode proves it. DEXIS ships samples.
            sample = dexis_dir / "Simulation" / "DCQ10.DEX"
            if sample.exists():
                try:
                    im = xf.read(sample)
                    report["sample_decode"] = f"{im.mode} {im.width}x{im.height}"
                except Exception as e:
                    report["sample_decode"] = (
                        f"FAILED ({e}); a wrong registration pair does this"
                    )
        except Exception as e:  # report, do not crash
            report["XfileInit"] = f"failed: {e!r}"
    root = default_root()
    report["data_root"] = str(root) if root else "unknown (set DEXIS_DATA_ROOT)"
    try:
        report["data_root_reachable"] = bool(root and root.exists())
    except OSError as e:
        report["data_root_reachable"] = f"no ({e.strerror})"
    report["ctypes_pointer_bytes"] = ctypes.sizeof(ctypes.c_void_p)
    print(
        json.dumps(report, indent=1)
        if a.json
        else "\n".join(f"{k:<22} {v}" for k, v in report.items())
    )


def current(a) -> None:
    from .current import current_patient, hostname, net_lock_holder, open_patients

    root = (DexisRoot(a.dexis_root) if a.dexis_root else DexisRoot()).root
    if a.all:
        rows = [
            {"host": p.host, "patient_id": p.patient_id} for p in open_patients(root)
        ]
        lock = net_lock_holder(root)
        if a.json:
            print(json.dumps({"open": rows, "net_lock": lock}, indent=1))
        else:
            for r in rows:
                print(f"{r['host']:<16} {r['patient_id']}")
            if not rows:
                print("no patient open on any workstation")
            if lock:
                print(f"net lock held by {lock}")
        return
    host = a.host or hostname()
    pid = current_patient(root, a.host)
    if a.json:
        print(json.dumps({"host": host, "patient_id": pid}, indent=1))
    elif pid is None:
        print(f"no patient open on {host}")
    else:
        print(f"{host}: patient {pid}")


def sweep(listing: Path, out: Path, per_cell: int, seed: int, kw: dict) -> None:
    """Stratified decode test: year x index side x power-of-two size band, smallest and
    largest per cell plus random picks. Rows carry the path; the report aggregates."""
    from .xfile import Xfile, upright

    def band(size: int) -> int:
        return 1 << max(16, int(math.log2(max(size, 1))))

    cells = defaultdict(list)
    for line in listing.read_text(encoding="utf-8").splitlines():
        path, date, size = line.split("\t")
        name = Path(path).name
        if not (name[0].isdigit() or name[0].lower() == "p"):
            continue
        side = "photo" if name[0].lower() == "p" else "xray"
        cells[(date[:4], side, band(int(size)))].append((path, int(size)))
    rng = random.Random(seed)
    picks = []
    for key, files in sorted(cells.items()):
        files.sort(key=lambda f: f[1])
        chosen = {files[0], files[-1]}
        rest = [f for f in files if f not in chosen]
        chosen.update(rng.sample(rest, min(max(per_cell - 2, 0), len(rest))))
        picks += [(key, f) for f in sorted(chosen)]
    print(f"{len(cells)} cells, {len(picks)} files", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    xf = Xfile(**kw)
    fields = [
        "year",
        "side",
        "band",
        "path",
        "size",
        "magic",
        "has_dexis_block",
        "header_width",
        "header_height",
        "bps",
        "type",
        "teeth",
        "acq_date",
        "acq_time",
        "rotation",
        "lux",
        "frames",
        "mode",
        "w",
        "h",
        "ms",
        "jpg",
        "error",
    ]
    with open(out / "sweep.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for i, ((year, side, b), (path, size)) in enumerate(picks, 1):
            row = {"year": year, "side": side, "band": b, "path": path, "size": size}
            try:
                with open(path, "rb") as f:
                    head = f.read(1 << 18)
                row["magic"] = head[:4].hex()
                row["has_dexis_block"] = b"DEXIS!" in head
                m = xf.meta(path)
                row.update({k: v for k, v in m.as_dict().items() if k in fields})
                row["lux"] = ",".join(map(str, m.lux))
                t0 = time.perf_counter()
                im = xf.read(path)
                row["ms"] = round((time.perf_counter() - t0) * 1000)
                row.update(mode=im.mode, w=im.width, h=im.height)
                im = upright(im, m.rotation)
                tag = hashlib.sha1(path.encode()).hexdigest()[:8]
                jpg = out / year / f"{side}_{b // 1024}k_{tag}.jpg"
                jpg.parent.mkdir(exist_ok=True)
                im.save(jpg, quality=90)
                row["jpg"] = jpg.name
            except Exception as e:
                row["error"] = repr(e)
            wr.writerow(row)
            fh.flush()
            if i % 20 == 0:
                print(f"{i}/{len(picks)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
