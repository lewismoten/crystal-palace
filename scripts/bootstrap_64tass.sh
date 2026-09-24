#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target="$root/tools/64tass"
mkdir -p "$target"
(
  cd "$target"
  apt download 64tass
  deb=$(printf '%s\n' 64tass_*.deb)
  dpkg-deb -x "$deb" .
  rm "$deb"
)
"$target/usr/bin/64tass" --version
