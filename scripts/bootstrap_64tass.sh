#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="$root/tools/64tass"
assembler="$target/usr/bin/64tass"

if [ ! -x "$assembler" ]; then
  if command -v apt >/dev/null 2>&1 && command -v dpkg-deb >/dev/null 2>&1; then
    mkdir -p "$target"
    (
      cd "$target"
      apt download 64tass
      deb=$(printf '%s\n' 64tass_*.deb)
      dpkg-deb -x "$deb" .
      rm "$deb"
    )
  elif command -v brew >/dev/null 2>&1; then
    if ! command -v 64tass >/dev/null 2>&1; then
      brew install tass64
    fi
    mkdir -p "$target/usr/bin"
    ln -sf "$(command -v 64tass)" "$assembler"
  else
    echo "64tass bootstrap needs apt/dpkg-deb (Debian/Ubuntu) or Homebrew (macOS)." >&2
    echo "On macOS: install Homebrew, then rerun this script; it will run: brew install tass64" >&2
    exit 1
  fi
fi

"$assembler" --version
