# Notes for anyone going further

Tools used: Ghidra 12 (headless, through an MCP bridge), plus small Python scripts that list each export's `ret N` and the strings it touches, and a 32-bit Python harness that calls the exports through ctypes against copies of the DLLs and the `C:\DEXIS\Simulation` samples.

## The calling convention trips Ghidra

Ghidra's default PE compiler spec mis-models these binaries. The pseudocode shows `unaff_ESI`, `void` parameters, and bare `FUN_` calls with no arguments; it labels the exports `__register (void)`. The `borlanddelphi` and `borlandcpp` specs do not fix it.

What is going on: the exports themselves are plain `__stdcall` (`[ebp+8]` for the first argument, `ret N` to clean up), but internal helpers take arguments in ebx, eax, ecx and esi and return in ebx, ecx and edx. Code is padded with `nop` x4 and `xchg ebx, ebx`. No stock Ghidra spec models it.

What works:

- `ret N` and the `[ebp+N]` reads give each export's signature. N / 4 is the argument count.
- Read the assembly to see where each parameter goes; setting the export to `__stdcall` with N parameters in Ghidra fixes the signature but the body still drops the parameters.
- A common helper shape: `cmp ebx, 0; je; mov [ebx], edx` is `if (out) *out = value` (xfile `0x41eaa4`, dexxdb `0x4049e0`).
- Success is `or al, 1`, failure `xor eax, eax`.
- To find a routine, follow the export that uses it rather than scanning for patterns. The edit curve had no FPU code and no obvious palette-fill loop; the 256-iteration loops a pattern scan finds are sensor raw correction.

## Oracles

When a routine is hard to read, make DEXIS compute it for you on scratch copies:

- `XimgTryExportFile` to `.bmp` turns an edited x-ray into a palette image whose palette is the edit curve (see [display.md](display.md)). Edit the window columns in a scratch `DEXIS.dat` to choose the input.
- DEXIS's own JPEG exports, recompressed through their own quantisation tables, give a zero-difference check on the whole x-ray chain.

## Read-only discipline

Every probe ran against copies: copies of the DLLs, a copied `Dexis.ini` pointed at a scratch data root, copies of a test patient's images. A file listing and hash of `C:\DEXIS` before and after each run caught anything that wrote. That is how the two dexxdb write hazards in [dexxdb.md](dexxdb.md) were found.
