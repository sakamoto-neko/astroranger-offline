#!/usr/bin/env python3
"""Binary patches for "Astro Ranger.exe" (AstroRanger v1.0.0.21 client).

  versus   - Versus Room always unlocked (skip the "clear the Secret Room once" lock)
  biscuit  - Biscuits can only go up, never down (spending is ignored)

Usage (run from anywhere):
    python astro_patch.py                         # game = current folder, apply all
    python astro_patch.py --game "D:/Games/AstroRanger"
    python astro_patch.py --game "D:/Games/AstroRanger/Astro Ranger.exe" versus
    python astro_patch.py --revert                # undo all

--game takes the game folder, any folder inside it, or the exe itself.

A backup "<exe>.bak" is written the first time the file is modified.
Every patch checks the original bytes first, so running it twice is harmless.
"""
import argparse
import os
import shutil
import sys

# file offset, original bytes, patched bytes, description
PATCHES = {
    "versus": [
        # 0x5E5970: jne -> jmp. The character-info packet handler sets the
        # "secret room not cleared" flag when packet byte +0xD88 is 0; always skip it.
        (0x1E5970, bytes.fromhex("750c"), bytes.fromhex("eb0c")),
    ],
    "biscuit": [
        # 0x5F2B20: SetBiscuit(lo, hi) rewritten to only store the new 64-bit value
        # when it is >= the current one.
        #   mov eax,ecx / mov ecx,[esp+4] / mov edx,[esp+8]
        #   cmp edx,[eax+2CDC1Ch] / jl skip / jg store
        #   cmp ecx,[eax+2CDC18h] / jb skip
        # store: mov [eax+2CDC18h],ecx / mov [eax+2CDC1Ch],edx
        # skip:  ret 8
        (0x1F2B20,
         bytes.fromhex("558bec51894dfc8b45fc8b4d08898818dc2c008b550c89901cdc2c008be55dc20800"
                       "cccccccccccccccccccccccccccc"),
         bytes.fromhex("89c88b4c24048b5424083b901cdc2c007c167f083b8818dc2c00720c"
                       "898818dc2c0089901cdc2c00c20800cccccccccc")),
    ],
}


def find_game(path=None):
    """Locate the AstroRanger game folder.

    Accepts the game folder, any folder or file inside it (e.g. the Datas folder or
    "Astro Ranger.exe"), or nothing (= the current folder). Walks up until it finds
    a folder holding "Astro Ranger.exe" or "Datas".
    """
    start = os.path.abspath(path or os.getcwd())
    if os.path.isfile(start):
        start = os.path.dirname(start)
    p = start
    while True:
        if os.path.isfile(os.path.join(p, "Astro Ranger.exe")) or os.path.isdir(os.path.join(p, "Datas")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            sys.exit(f"Can't find the AstroRanger game folder from {start}.\n"
                     "Run this from the game folder or pass it with --game.")
        p = parent


def apply(path, names, revert=False):
    for n in names:
        for _, o, p in PATCHES[n]:
            assert len(o) == len(p)
    data = bytearray(open(path, "rb").read())
    changed = False
    for name in names:
        for off, orig, new in PATCHES[name]:
            src, dst = (new, orig) if revert else (orig, new)
            cur = bytes(data[off:off + len(src)])
            if cur == dst:
                print(f"[{name}] already {'reverted' if revert else 'applied'} at 0x{off:X}")
            elif cur == src:
                data[off:off + len(src)] = dst
                changed = True
                print(f"[{name}] {'reverted' if revert else 'patched'} at 0x{off:X}")
            else:
                sys.exit(f"[{name}] unexpected bytes at 0x{off:X} - different exe version? Nothing written.")
    if changed:
        bak = path + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
            print("backup:", bak)
        open(path, "wb").write(data)


def find_exe(path):
    if path and os.path.isfile(path):
        return os.path.abspath(path)
    exe = os.path.join(find_game(path), "Astro Ranger.exe")
    if not os.path.isfile(exe):
        sys.exit(f"{exe} not found")
    return exe


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Patch Astro Ranger.exe",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("patches", nargs="*",
                    help="patches to apply: " + ", ".join(PATCHES) + " (default: all)")
    ap.add_argument("--game", help="game folder or exe (default: current folder)")
    ap.add_argument("--revert", action="store_true", help="undo the patches")
    a = ap.parse_args()
    for n in a.patches:
        if n not in PATCHES:
            ap.error(f"unknown patch '{n}'. Available: {', '.join(PATCHES)}")
    exe = find_exe(a.game)
    print("exe:", exe)
    apply(exe, a.patches or list(PATCHES), revert=a.revert)
