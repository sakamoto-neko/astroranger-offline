#!/bin/sh
# Build AstroRanger_Play.exe with MinGW-w64 (Debian/Ubuntu: apt install gcc-mingw-w64-i686).
# Works from any folder; the exe is written next to this script.
#   ./build.sh                 uses aricon.ico next to this script, if present
#   ./build.sh /path/to/game   copies the icon from the game folder
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ICON=""
if [ -f "$HERE/aricon.ico" ]; then ICON="$HERE/aricon.ico"
elif [ -n "$1" ] && [ -f "$1/aricon.ico" ]; then ICON="$1/aricon.ico"
fi
if [ -n "$ICON" ]; then
    cp "$ICON" "$TMP/aricon.ico"
    cp "$HERE/res.rc" "$TMP/res.rc"
    (cd "$TMP" && i686-w64-mingw32-windres res.rc -O coff -o res.o)
    RES="$TMP/res.o"
else
    echo "note: aricon.ico not found, building without an icon"
    RES=""
fi
i686-w64-mingw32-gcc -O2 -s -mwindows -static "$HERE/launcher.c" $RES \
    -o "$HERE/AstroRanger_Play.exe" -liphlpapi -lws2_32
echo "built $HERE/AstroRanger_Play.exe"
