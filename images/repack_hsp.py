"""Rebuild AstroRanger .hsp archives with your edited PNG images.

    python repack_hsp.py [--game DIR] [--edit DIR] [--out DIR | --install]

  --game     game folder, or any folder inside it (default: current folder)
  --edit     folder with edited PNGs (default: ./edit), laid out as
             <archive>.hsp/<path inside archive>.png, e.g.
             edit/UI/Mid/Option.hsp/Datas/Texture/UI/Mid/Option/option_text_bgm.tga.png
  --out      where rebuilt archives go (default: ./repacked)
  --install  also copy the rebuilt archives into the game's Datas/Texture;
             the originals are first saved to <game>/Image_Backup

Each PNG is converted back to a 32-bit RLE TGA and must keep its original size.
Images whose pixels didn't change keep their original bytes.
"""
import argparse, io, os, shutil, struct, sys, zlib

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

from PIL import Image

def read_hsp(path):
    d = open(path, 'rb').read()
    assert d[:4] == b' PSH', 'not an HSP archive'
    ver, cnt, unk = struct.unpack('<III', d[4:16])
    ents = []
    for i in range(cnt):
        e = d[16 + i*140: 16 + (i+1)*140]
        name = e[:128]
        cs, us, off = struct.unpack('<III', e[128:140])
        ents.append([name, cs, us, d[off:off+cs]])
    return ver, unk, ents

def write_hsp(path, ver, unk, ents):
    out = bytearray(b' PSH' + struct.pack('<III', ver, len(ents), unk))
    off = 16 + 140*len(ents)
    hdr = bytearray(); body = bytearray()
    for name, cs, us, blob in ents:
        hdr += name + struct.pack('<III', len(blob), us, off + len(body))
        body += blob
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    open(path, 'wb').write(out + hdr + body)

def png_to_tga(im):
    b = io.BytesIO(); im.save(b, format='TGA', rle=True); return b.getvalue()

def main(datas, edit, outdir):
    done = []
    for root, dirs, files in os.walk(edit):
        if not root.lower().endswith('.hsp'):
            continue
        rel = os.path.relpath(root, edit)
        src = os.path.join(datas, 'Texture', rel)
        ver, unk, ents = read_hsp(src)
        byname = {e[0].split(b'\0')[0].decode('cp949').lower().replace('\\', '/'): e for e in ents}
        changed = 0
        for r2, _, fs in os.walk(root):
            for f in fs:
                if not f.lower().endswith('.png'):
                    continue
                inner = os.path.relpath(os.path.join(r2, f), root)[:-4].replace('\\', '/')
                key = inner.lower()
                if key not in byname:
                    print('  ! not in archive:', inner); continue
                e = byname[key]
                orig = zlib.decompress(e[3]) if e[1] != e[2] else e[3]
                ref = Image.open(io.BytesIO(orig)).convert('RGBA')
                im = Image.open(os.path.join(r2, f)).convert('RGBA')
                if im.size != ref.size:
                    raise SystemExit(f'{inner}: size {im.size} differs from original {ref.size}')
                if im.tobytes() == ref.tobytes():
                    continue          # untouched image: keep original bytes
                tga = png_to_tga(im)
                e[2] = len(tga); e[3] = zlib.compress(tga, 9); changed += 1
        dst = os.path.join(outdir, rel)
        write_hsp(dst, ver, unk, ents)
        print(f'{rel}: {changed} image(s) replaced -> {dst}')
        done.append(rel)
    if not done:
        print(f'no <archive>.hsp folders found in {edit}')
    return done

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Repack .hsp archives with edited PNGs',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--game', help='game folder (default: current folder)')
    ap.add_argument('--edit', default='edit', help='folder with edited PNGs')
    ap.add_argument('--out', default='repacked', help='output folder')
    ap.add_argument('--install', action='store_true', help='copy rebuilt archives into the game')
    a = ap.parse_args()
    game = find_game(a.game)
    datas = os.path.join(game, 'Datas')
    if not os.path.isdir(a.edit):
        sys.exit(f'{a.edit} not found')
    out = os.path.abspath(a.out)
    if out.startswith(os.path.join(datas, 'Texture')):
        sys.exit('--out must not be inside the game\'s Texture folder; use --install instead')
    print('game:', game)
    done = main(datas, a.edit, out)
    if a.install:
        backup = os.path.join(game, 'Image_Backup')
        for rel in done:
            dst = os.path.join(datas, 'Texture', rel)
            bak = os.path.join(backup, rel)
            if not os.path.exists(bak):
                os.makedirs(os.path.dirname(bak), exist_ok=True)
                shutil.copy2(dst, bak)
            shutil.copy2(os.path.join(out, rel), dst)
        print(f'installed {len(done)} archive(s) (originals in {backup})')
