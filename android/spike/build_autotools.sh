#!/usr/bin/env bash
set -euo pipefail

SPIKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$SPIKE_DIR/tools/autotools"
SRC="$SPIKE_DIR/tools/build"
mkdir -p "$PREFIX" "$SRC"

export PATH="$PREFIX/bin:$PATH"

build_pkg() {
    local name="$1" url="$2"
    echo "=== building $name ==="
    cd "$SRC"
    curl -L --retry 3 -o "$name.tar.gz" "$url"
    if [ -d "$name" ]; then mv "$name" "$SRC/$name.old.$$"; fi
    tar xzf "$name.tar.gz"
    cd "$name"
    ./configure --prefix="$PREFIX"
    make -j"$(nproc)"
    make install
    echo "=== $name installed ==="
}

build_pkg m4-1.4.21 https://ftp.gnu.org/gnu/m4/m4-1.4.21.tar.gz
build_pkg autoconf-2.72 https://ftp.gnu.org/gnu/autoconf/autoconf-2.72.tar.gz
build_pkg automake-1.17 https://ftp.gnu.org/gnu/automake/automake-1.17.tar.gz
build_pkg libtool-2.4.7 https://ftp.gnu.org/gnu/libtool/libtool-2.4.7.tar.gz

echo "=== versions ==="
autoreconf --version | head -1
automake --version | head -1
aclocal --version | head -1
libtoolize --version | head -1
m4 --version | head -1
echo "=== ac dir ==="
ls "$(aclocal --print-ac-dir)" | grep -iE "libtool|ltdl" | head
