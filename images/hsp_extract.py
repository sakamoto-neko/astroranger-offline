#!/usr/bin/env python3
"""Unpack AstroRanger .hsp archives (" PSH" format).

    python hsp_extract.py [SOURCE] [--game DIR] [--out DIR] [--png]

SOURCE is one .hsp file or a folder of them. Without it, every archive in the
game's Datas/Texture folder is unpacked (game = --game, or the current folder
or one of its parents). Default output: ./textures

Format: 16-byte header (" PSH", version, count, 0), then <count> entries of
140 bytes (char name[128], u32 packed size, u32 real size, u32 absolute offset),
then the data. Entries are zlib streams (stored raw when packed == real size).
With --png, images are also saved as PNG next to the originals (needs Pillow).
"""
import argparse, glob, os, struct, sys, zlib

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



def read_hsp(path):
    d = open(path, "rb").read()
    if d[:4] != b" PSH":
        raise ValueError(f"{path}: not an HSP archive")
    ver, cnt, _ = struct.unpack("<III", d[4:16])
    for i in range(cnt):
        e = d[16 + i * 140: 16 + (i + 1) * 140]
        name = e[:128].split(b"\0")[0].decode("cp949")
        cs, us, off = struct.unpack("<III", e[128:140])
        raw = d[off:off + cs]
        data = raw if cs == us else zlib.decompress(raw)
        yield name, data


def main(src, out, png=False):
    files = [src] if os.path.isfile(src) else glob.glob(os.path.join(src, "**", "*.hsp"), recursive=True)
    total = 0
    for f in files:
        n = 0
        for name, data in read_hsp(f):
            p = os.path.join(out, name.replace("\\", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(data)
            if png and p.lower().endswith((".tga", ".dds", ".bmp", ".jpg", ".png")):
                from PIL import Image
                try:
                    Image.open(p).convert("RGBA").save(p + ".png")
                except Exception as ex:
                    print("  ! cannot convert", name, ex)
            n += 1
        print(f"{n:5d}  {f}")
        total += n
    print(f"{total} files -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Unpack .hsp archives",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("source", nargs="?", help=".hsp file or folder (default: <game>/Datas/Texture)")
    ap.add_argument("--game", help="game folder (default: current folder)")
    ap.add_argument("--out", default="textures", help="output folder")
    ap.add_argument("--png", action="store_true", help="also save PNG copies of images")
    a = ap.parse_args()
    src = a.source or os.path.join(find_game(a.game), "Datas", "Texture")
    if not os.path.exists(src):
        sys.exit(f"{src} not found")
    main(src, os.path.abspath(a.out), a.png)
