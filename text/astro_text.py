#!/usr/bin/env python3
"""Extract and replace the Korean text in AstroRanger.

Run from anywhere. --game takes the game folder or any folder/file inside it;
without it, the current folder (or one of its parents) is used.

    python astro_text.py extract [--game DIR] [--out DIR]
        Writes korean_strings_all.csv (every occurrence, with offset and room)
        and korean_strings_unique.csv (each text once). Default out: ./korean_strings

    python astro_text.py apply [--game DIR] [--table TSV] [--out DIR | --install]
        Writes translated copies of the game files, keeping the game's folder
        layout. Default table: translation_en.tsv next to this script.
        Default out: ./translated_files. With --install the files go straight
        into the game folder; the originals are first copied to
        <game>/Korean_Backup (existing backups are never overwritten).

translation.tsv is UTF-8, one entry per line:   <korean><TAB><english>
Newlines inside a string are written as \\n. Lines starting with # are ignored.

Files handled: "Astro Ranger.exe", Datas/Table/ARDB.gin, Datas/UI/*.int, Option.ini.
All text is CP949. Every replacement is done in place (no file offsets move):
  * exe:  up to the string's 4-byte-aligned slot (strings in .data: their buffer)
  * ARDB: up to the fixed field size (160 / 260 bytes)
  * .int: the original byte length (strings there are length-prefixed)
Translations that don't fit are skipped and listed.
"""
import argparse
import csv
import glob
import os
import re
import shutil
import struct
import sys

EXE = "Astro Ranger.exe"
ARDB = "Datas/Table/ARDB.gin"
EXE_TEXT = (0x281000, 0x2F2000)            # .rdata + .data
ARDB_FILTER = (0x1A49A8, 0x1BAC1C)         # chat word filter / reserved names: keep Korean
KEEP = {"맑은 고딕 Bold", "굴림체"}            # font face names

# a run of text bytes (ASCII or CP949 double-byte) that ends at a NUL
RUN = re.compile(rb"(?:[\x20-\x7e\t\r\n]|[\x81-\xfe][\x41-\x5a\x61-\x7a\x81-\xfe])+(?=\x00)")
STRICT = re.compile(rb"(?:[\x20-\x7e\t\r\n]|[\xb0-\xc8][\xa1-\xfe]|[\xa1-\xac][\xa1-\xfe])+(?=\x00)")


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


def hangul(c):
    return "\uac00" <= c <= "\ud7a3"


def ks(c):  # common (KS X 1001) syllable
    if not hangul(c):
        return False
    b = c.encode("cp949")
    return 0xB0 <= b[0] <= 0xC8 and 0xA1 <= b[1] <= 0xFE


def game_files(game):
    out = [EXE, ARDB] + ["Datas/UI/" + os.path.basename(p)
                         for p in sorted(glob.glob(os.path.join(game, "Datas", "UI", "*.int")))]
    return [f for f in out if os.path.exists(os.path.join(game, f))]


def zero_run(d, o, n, cap=1024):
    e = o + n
    while e < len(d) and d[e] == 0 and e - o < cap:
        e += 1
    return e - o


def limit_for(f, d, o, n):
    """How many bytes (without the NUL) a replacement at offset o may use."""
    cap = zero_run(d, o, n)
    if f == EXE:
        if o >= 0x2DF000:                      # char arrays in .data
            return cap - 1
        end = (o + n + 1 + 3) // 4 * 4         # compiler pads strings to 4 bytes
        return min(end - o - 1, cap - 1)
    if f == ARDB:
        return max(min(cap - 1, 259) if cap >= 160 else cap - 1, n)
    return n                                   # .int: length-prefixed, keep size


def candidates(f, d):
    """(offset, raw bytes, text) for every NUL-terminated text run, all suffixes."""
    lo, hi = EXE_TEXT if f == EXE else (0, len(d))
    for m in RUN.finditer(d, lo, hi):
        b = m.group()
        try:
            t = b.decode("cp949")
        except UnicodeDecodeError:
            continue
        if not any(hangul(c) for c in t):
            continue
        pos = 0
        for i, ch in enumerate(t):             # every character boundary = a possible start
            yield m.start() + pos, b[pos:], t[i:]
            pos += len(ch.encode("cp949"))


# ------------------------------------------------------------------ extract
def extract(game, out):
    rows = []
    for f in game_files(game):
        d = open(os.path.join(game, f), "rb").read()
        lo, hi = EXE_TEXT if f == EXE else (0, len(d))
        for m in RUN.finditer(d, lo, hi):
            b = m.group()
            try:
                t = b.decode("cp949")
            except UnicodeDecodeError:
                continue
            i = 0                                   # trim leading binary junk
            while i < len(t) and not (hangul(t[i]) or (t[i].isascii() and t[i].isprintable())):
                i += 1
            while i < len(t) and not t[i].isascii() and not ks(t[i]):
                i += 1
            t2 = t[i:]
            h = sum(ks(c) for c in t2)
            non_ascii = [c for c in t2 if not c.isascii()]
            if h < 2 or (non_ascii and h / len(non_ascii) < 0.9):
                continue
            o = m.start() + len(t[:i].encode("cp949"))
            n = len(b) - (o - m.start())
            if f == ARDB and ARDB_FILTER[0] <= o <= ARDB_FILTER[1]:
                note = "chat filter / reserved name"
            elif t2 in KEEP:
                note = "font name"
            elif ".jpg" in t2 or ".tga" in t2:
                note = "file name"
            else:
                note = ""
            rows.append([f, "0x%X" % o, n, limit_for(f, d, o, n), note, t2])
    ini = os.path.join(game, "Option.ini")
    if os.path.exists(ini):
        for i, line in enumerate(open(ini, "rb").read().split(b"\r\n")):
            k, _, v = line.decode("cp949", "replace").partition("\t")
            if any(hangul(c) for c in v):
                rows.append(["Option.ini", "line %d" % (i + 1), len(v.encode("cp949")), "", k, v])
    os.makedirs(out, exist_ok=True)
    esc = lambda s: s.replace("\r", "\\r").replace("\n", "\\n")
    with open(os.path.join(out, "korean_strings_all.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "offset", "bytes", "max_bytes", "note", "korean"])
        for r in rows:
            w.writerow(r[:5] + [esc(r[5])])
    uniq = {}
    for r in rows:
        u = uniq.setdefault(r[5], [0, [], r[3] or 999])
        u[0] += 1
        u[2] = min(u[2], r[3] or 999)
        if len(u[1]) < 5:
            u[1].append(f"{r[0]}@{r[1]}")
    with open(os.path.join(out, "korean_strings_unique.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["korean", "occurrences", "max_bytes", "locations", "english"])
        for k, (n, loc, lim) in uniq.items():
            w.writerow([esc(k), n, lim, " | ".join(loc), ""])
    print(f"{len(rows)} strings ({len(uniq)} unique) -> {out}")


# -------------------------------------------------------------------- apply
def load_table(path):
    table = {}
    for line in open(path, encoding="utf-8-sig"):
        line = line.rstrip("\r\n")
        if not line or line.startswith("#") or "\t" not in line:
            continue
        ko, en = line.split("\t", 1)
        un = lambda s: s.replace("\\n", "\n").replace("\\r", "\r")
        table[un(ko)] = un(en)
    return table


def patch_hyuk_name(d):
    """The name "혁" is copied by inlined code as 3 fixed bytes; rewrite it to store "Hyuk"."""
    o = 0x1ABC7D
    old = bytes.fromhex("668b15d0426b00668995c4faffffa0d2426b008885c6faffff"
                        "b94000000033c08dbdc7faffff f3abaa".replace(" ", ""))
    new = bytes.fromhex("c785c4faffff4879756b" + "90" * 15 +
                        "b94000000033c08dbdc8faffff f3ab90".replace(" ", ""))
    if d[o:o + len(old)] == old:
        d[o:o + len(new)] = new
        return True
    return d[o:o + len(new)] == new


def apply(game, table_path, out):
    table = load_table(table_path)
    skipped, counts, written_files = [], {}, []
    for f in game_files(game):
        d = bytearray(open(os.path.join(game, f), "rb").read())
        taken = []
        n_done = 0
        for o, b, t in candidates(f, bytes(d)):
            if t not in table or t in KEEP:
                continue
            if f == ARDB and ARDB_FILTER[0] <= o <= ARDB_FILTER[1]:
                continue
            if any(a <= o < z for a, z in taken):          # part of a string already done
                continue
            n = len(b)
            en = table[t].encode("cp949")
            lim = limit_for(f, d, o, n)
            if f == EXE and t == "혁":                      # handled by patch_hyuk_name
                continue
            if len(en) > lim:
                skipped.append((f, "0x%X" % o, t, table[t], len(en), lim))
                continue
            if "Datas/UI/" in f:
                d[o:o + n + 1] = en + b"\0" * (n + 1 - len(en))
                span = n + 1
            else:
                span = max(n, len(en)) + 1
                d[o:o + span] = en + b"\0" * (span - len(en))
            taken.append((o, o + span))
            n_done += 1
        if f == EXE and "혁" in table:
            if not patch_hyuk_name(d):
                print("warning: could not apply the Hyuk name code patch (different exe?)")
        if n_done:
            p = os.path.join(out, f)
            os.makedirs(os.path.dirname(p) or out, exist_ok=True)
            open(p, "wb").write(d)
            written_files.append(f)
        counts[f] = n_done
    ini = os.path.join(game, "Option.ini")
    if os.path.exists(ini):
        lines = []
        for line in open(ini, "rb").read().split(b"\r\n"):
            k, sep, v = line.decode("cp949").partition("\t")
            lines.append((k + sep + table.get(v, v)).encode("cp949"))
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "Option.ini"), "wb").write(b"\r\n".join(lines))
        written_files.append("Option.ini")
    for f, c in counts.items():
        if c:
            print(f"{c:5d}  {f}")
    if skipped:
        print(f"\n{len(skipped)} translation(s) too long, left in Korean:")
        for s in skipped:
            print(f"  {s[0]} {s[1]}  {s[2]!r} -> {s[3]!r}  ({s[4]} > {s[5]} bytes)")
    print(f"\n{len(written_files)} file(s) written to {out}")
    return written_files


def install(game, out, files):
    backup = os.path.join(game, "Korean_Backup")
    for f in files:
        src, dst, bak = os.path.join(out, f), os.path.join(game, f), os.path.join(backup, f)
        if os.path.exists(dst) and not os.path.exists(bak):
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
    print(f"installed into {game} (originals in {backup})")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="AstroRanger text tool",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="list the Korean strings")
    e.add_argument("--game", help="game folder (default: current folder)")
    e.add_argument("--out", default="korean_strings", help="output folder")
    p = sub.add_parser("apply", help="write translated game files")
    p.add_argument("--game", help="game folder (default: current folder)")
    p.add_argument("--table", default=os.path.join(here, "translation_en.tsv"), help="translation TSV")
    p.add_argument("--out", default="translated_files", help="output folder")
    p.add_argument("--install", action="store_true", help="also copy the result into the game folder")
    a = ap.parse_args()
    game = find_game(a.game)
    print("game:", game)
    if a.cmd == "extract":
        extract(game, os.path.abspath(a.out))
    else:
        if os.path.abspath(a.out) == game:
            sys.exit("--out must not be the game folder itself; use --install instead")
        files = apply(game, a.table, os.path.abspath(a.out))
        if a.install:
            install(game, os.path.abspath(a.out), files)
