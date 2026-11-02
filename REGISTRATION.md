# Registration pair

`xfile.dll` decodes nothing until it is initialised with a registration name and code it accepts. With a wrong pair, initialisation still reports success, and every decode then fails. `dexport doctor` shows which case you are in by decoding one of DEXIS's own sample images.

dexport does not include a pair and does not try to find one. Use the one that belongs to your own licensed DEXIS install, put in one of these places (the first one found wins):

1. The environment variable `DEXIS_REGISTRATION`, as `NAME:CODE`.
2. The file `%APPDATA%\dexport\registration.txt`, holding `NAME:CODE` on one line. Lines starting with `#` are ignored. Set `DEXIS_REGISTRATION_FILE` to use a different file, for example one on a share that several PCs in your office read.

```powershell
mkdir $env:APPDATA\dexport
Set-Content $env:APPDATA\dexport\registration.txt "NAME:CODE"
dexport doctor
```

If you don't have one, DEXIS documents that third-party programs get a registration code from DEXIS Customer Care.

Keep the pair out of anything you publish or share, including issues on this repo. The `.gitignore` here ignores `registration.txt`.
