#!/usr/bin/env python3
"""Find images that contain Korean text, using Tesseract OCR (kor).

    python find_korean_images.py [EXTRACTED] [--out DIR]

EXTRACTED defaults to ./textures (hsp_extract.py's default output);
results go to ./ocr unless --out is given.

Run hsp_extract.py first. Writes ocr_scores.csv (images ranked by how much
Korean was recognised) and contact sheets of the candidates for a visual check.
OCR misses stylised lettering and gives some false positives, so always review
the sheets: the final hand-checked list for this game is korean_images.txt.

Needs: Pillow, and the tesseract command with Korean data
(Debian/Ubuntu: apt install tesseract-ocr tesseract-ocr-kor).
"""
import argparse, csv, glob, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw

EXTS = (".tga", ".dds", ".bmp", ".png", ".jpg")


def ocr(path):
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        return path, 0, ""
    bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
    bg.alpha_composite(im)
    g = bg.convert("L")
    if max(g.size) < 600:
        g = g.resize((g.width * 2, g.height * 2))
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "i.png")
        g.save(p)
        r = subprocess.run(["tesseract", p, "stdout", "-l", "kor", "--psm", "11", "tsv"],
                           capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    words, score = [], 0
    for row in csv.reader(r.stdout.splitlines()[1:], delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(row) < 12:
            continue
        t, conf = row[11].strip(), float(row[10])
        h = sum("가" <= c <= "힣" for c in t)
        if h and conf >= 50:
            words.append(t)
            score += h
    return path, score, " ".join(words)


def sheet(files, out, cell=200, cols=6):
    rows = (len(files) + cols - 1) // cols
    S = Image.new("RGB", (cols * cell, rows * (cell + 14)), (60, 60, 60))
    dr = ImageDraw.Draw(S)
    for k, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        im.thumbnail((cell, cell))
        bg = Image.new("RGBA", im.size, (110, 110, 110, 255))
        bg.alpha_composite(im)
        x, y = (k % cols) * cell, (k // cols) * (cell + 14)
        S.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 2, y + cell), f"{k}:" + os.path.basename(f)[:30], fill=(255, 255, 0))
    S.save(out)


def main(src, out):
    files = [f for f in glob.glob(os.path.join(src, "**", "*"), recursive=True)
             if f.lower().endswith(EXTS) and not f.lower().endswith(".tga.png")]
    os.makedirs(out, exist_ok=True)
    with ThreadPoolExecutor(os.cpu_count()) as ex:
        res = sorted(ex.map(ocr, files), key=lambda r: -r[1])
    with open(os.path.join(out, "ocr_scores.csv"), "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["image", "korean_chars", "ocr_text"])
        w.writerows([[os.path.relpath(p, src), s, t] for p, s, t in res])
    cand = [p for p, s, _ in res if s >= 1]
    for i in range(0, len(cand), 42):
        sheet(cand[i:i + 42], os.path.join(out, f"candidates_{i // 42 + 1:02d}.jpg"))
    print(f"{len(files)} images scanned, {len(cand)} candidates -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Find images with Korean text",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("source", nargs="?", default="textures", help="folder of extracted images")
    ap.add_argument("--out", default="ocr", help="output folder")
    a = ap.parse_args()
    if not os.path.isdir(a.source):
        sys.exit(f"{a.source} not found - run hsp_extract.py first or pass the folder")
    if not shutil.which("tesseract"):
        sys.exit("tesseract not found (install tesseract-ocr and tesseract-ocr-kor)")
    main(a.source, os.path.abspath(a.out))
