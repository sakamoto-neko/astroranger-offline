# AstroRanger Offline Tools

Modding tools for **AstroRanger** (아스트로레인저), a 2008 Korean PC rhythm game by E-ZEN / Biscuit Soft, played offline through the fan-made local server `Start.exe` ("Goodev.net ATconnector").

These mods work with files with these checksums:
**`astrorangerclient.exe`**
* CRC32: 7DE9636A
* MD5: 3CDBC04174DB0AF7ECF84844C13E7831
**`Start.exe`** (from Single Patch.7z)
* CRC32: 5134CFE7
* MD5: B259CF40E3C092820C78075A93B1250C

| Tool | What it does |
|---|---|
| [`launcher/`](launcher) | One-click launcher: starts the local server hidden, presses its *Start Game* button, closes it when you quit |
| [`patches/`](patches) | Exe patches: Versus Room always unlocked, biscuits never decrease |
| [`text/`](text) | Extract every Korean string and write translations back in place (full English translation included) |
| [`images/`](images) | Unpack `.hsp` texture archives, find images with Korean text, and repack edited PNGs |

All tools were written against the client **Astro Ranger v1.0.0.21** (`Astro Ranger.exe`, 3,244,032 bytes). The scripts check the original bytes before changing anything and stop if they don't match.

## Finding the game folder

Every tool works from **any folder** and with the game installed **anywhere**:

- **Python tools** take `--game <path>`. The path can be the game folder, any folder inside it (such as `Datas`), or `Astro Ranger.exe` itself. Without `--game`, they look in the current folder and its parents. So running a tool from inside the game folder needs no arguments, and running it from elsewhere just needs `--game`.
- **The launcher** uses its own folder by default. It can also live elsewhere and point at the game with `GameDir=` in its `.ini`, or with a folder passed on its command line.
- **Default output folders** are created in the current folder. Translation tables and other data files are found next to the scripts, wherever the repo is.

> **Back up your game folder first.** Every tool writes to a separate output folder by default, and `--install` / exe patches save the originals first (`Korean_Backup`, `Image_Backup`, `.bak`), but a full copy is the safest undo.

---

## Requirements

- **Python 3.8+** for the scripts
- **[Pillow](https://pypi.org/project/Pillow/)** for the image tools: `pip install pillow`
- **Tesseract OCR with Korean data** (only for `find_korean_images.py`): `apt install tesseract-ocr tesseract-ocr-kor`
- **MinGW-w64** (only to rebuild the launcher): `apt install gcc-mingw-w64-i686`

---

## Launcher

Normally you open `Start.exe` and press its bottom-right button to start the game. `AstroRanger_Play.exe` does that in one click:

1. Closes any leftover `Start.exe`, then starts a fresh one with its window off-screen
2. Waits until the server is listening (port from `config\loginsvr.cfg`, 6760 by default)
3. Presses the server's own launch button, so the server does its normal login setup
4. Hides the server once the game has connected, and closes it when the game exits

> `Start.exe` contains a hidden browser control that loads the E-ZEN `ARWeb` login add-on. Starting the server fully hidden stops it from loading, and the game then shows no channels. That's why the window is moved off-screen rather than hidden at startup.

**Build:** run `launcher/build.sh /path/to/game` from any folder. The game path is only used to copy the icon (`aricon.ico`). Without it, the script uses an `aricon.ico` placed next to it, or builds without an icon. The exe is written next to `build.sh`.

**Install:** copy `AstroRanger_Play.exe` and `AstroRanger_Play.ini` into the game folder. To keep the launcher somewhere else, set `GameDir=` in the `.ini`, or start it with the game folder as its argument (useful for shortcuts):

```
AstroRanger_Play.exe "D:\Games\AstroRanger"
```

**Settings** (`AstroRanger_Play.ini`):

| Key | Default | Meaning |
|---|---|---|
| `GameDir` | *(empty)* | Game folder: absolute, or relative to the launcher. Empty = the launcher's own folder. |
| `ShowServer` | `0` | `1` keeps the server window on screen |
| `HideServerAfterConnect` | `1` | Hide the server once the game has logged in |
| `CloseServerOnExit` | `1` | Close `Start.exe` when the game exits |
| `ServerWaitSeconds` | `15` | Max wait for the server to start |
| `ExtraDelayMs` | `2500` | Extra wait before pressing the launch button |
| `Server` / `Game` | `Start.exe` / `Astro Ranger.exe` | File names |

---

## Exe patches

```sh
python patches/astro_patch.py --game "D:/Games/AstroRanger"            # apply all
python patches/astro_patch.py --game "D:/Games/AstroRanger" versus     # apply one
python patches/astro_patch.py --game "D:/Games/AstroRanger" --revert   # undo
python /path/to/astro_patch.py                                         # from inside the game folder
```

| Patch | Offset | Change |
|---|---|---|
| `versus` | `0x1E5970` | `jne` → `jmp`. The character-info handler sets a *Secret Room not cleared* lock when packet byte `+0xD88` is 0, and `Start.exe` always sends 0. The lock is never set now. |
| `biscuit` | `0x1F2B20` | The biscuit setter (64-bit value at `this+0x2CDC18`) is rewritten to store the new value only if it is **≥** the current one, so spending is ignored and rewards still add up. |

---

## Text translation

```sh
# list every Korean string with its location and how much room it has  (-> ./korean_strings)
python text/astro_text.py extract --game "D:/Games/AstroRanger"

# write translated copies of the game files, same layout as the game  (-> ./translated_files)
python text/astro_text.py apply --game "D:/Games/AstroRanger"

# ...or install straight into the game; originals go to <game>/Korean_Backup
python text/astro_text.py apply --game "D:/Games/AstroRanger" --install

# your own translation table / output folder
python text/astro_text.py apply --game "D:/Games/AstroRanger" --table my_table.tsv --out somewhere
```

`translation_en.tsv` is a complete English translation (about 1,960 entries): system messages, tutorial and story dialogue, about 1,300 item names and descriptions, song titles, and UI labels. `apply` uses it by default, wherever the repo is. Edit it or make your own. The format is one `korean<TAB>english` pair per line, with `\n` for line breaks.

**Where the text lives** (all CP949):

| File | Contents | How it's replaced |
|---|---|---|
| `Astro Ranger.exe` | System messages, tutorial dialogue, default chat macros | In place, up to the string's 4-byte-aligned slot (`.data` char arrays: their buffer size) |
| `Datas/Table/ARDB.gin` | Songs, items and descriptions, NPC story, emote keywords | Fixed-size fields (160 / 260 bytes) |
| `Datas/UI/*.int` | Button and label text | Length-prefixed, so kept at the original byte length |
| `Option.ini` | Chat macros | Plain text |

Nothing in the files is moved. A translation that doesn't fit is skipped and listed. These are left in Korean on purpose:

- **The chat filter and reserved-name list** in `ARDB.gin` (`0x1A49A8`–`0x1BAC1C`), since it matches what players type
- **Font face names**
- **Image file names** inside the `.int` files

Two details in the exe:

- **Inlined string copies.** MSVC copied a few short strings with fixed-size moves. They were checked: longer English still ends correctly because the destination buffer is zeroed right after the copy.
- **The name "혁" (Hyuk)** is copied as exactly 3 bytes, so `apply` also rewrites that code (at `0x1ABC7D`) to store `"Hyuk"` and moves the buffer clear by one byte.

---

## Images

Textures are stored in `.hsp` archives with this layout:

```
" PSH" u32 version, u32 count, u32 0
count × { char name[128]; u32 packedSize; u32 size; u32 offset; }   // offset is absolute
data: zlib streams (stored raw when packedSize == size)
```

```sh
# 1. unpack every archive in <game>/Datas/Texture  (-> ./textures; --png adds PNG copies)
python images/hsp_extract.py --game "D:/Games/AstroRanger" --png
#    or a single archive / folder of archives
python images/hsp_extract.py "D:/Games/AstroRanger/Datas/Texture/UI/Mid/Option.hsp" --out option

# 2. optional: OCR scan of ./textures for Korean text, with contact sheets  (-> ./ocr)
python images/find_korean_images.py

# 3. put edited PNGs in ./edit, then rebuild the archives  (-> ./repacked)
python images/repack_hsp.py --game "D:/Games/AstroRanger"
#    ...or install them straight into the game; originals go to <game>/Image_Backup
python images/repack_hsp.py --game "D:/Games/AstroRanger" --install
```

Every step has `--out` / `--edit` options if you want other folders. `korean_images.txt` lists the **340 UI images** (all 32-bit TGA) confirmed by hand to contain Korean text. `repack_hsp.py` expects edited PNGs at `edit/<archive>.hsp/<path inside archive>.png`, for example:

```
edit/UI/Mid/Option.hsp/Datas/Texture/UI/Mid/Option/option_text_bgm.tga.png
```

It converts the PNGs back to 32-bit RLE TGA. Only images whose pixels changed are replaced, so an archive with no edits is rebuilt byte-identical. Each edited image must keep its original size.

Not covered: the cutscene videos (`Datas/Cutscene/*.bik`, Bink format).

---

## Credits

- The game © E-ZEN Entertainment / Biscuit Soft
- `Start.exe` local server by Goodev.net

These tools contain no game data apart from the translated strings in `translation_en.tsv`. You need your own copy of the game.
