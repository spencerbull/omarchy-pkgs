#!/bin/bash
set -euo pipefail

# Omarchy's offline installer manifest includes yay-debug. Arch Linux ARM's
# makepkg defaults disable split debug packages, so opt this package in.
case $(grep -m1 '^options=' PKGBUILD) in
  'options=(!lto)')
    sed -i 's/^options=(!lto)$/options=(!lto debug)/' PKGBUILD
    ;;
  'options=(!lto debug)')
    ;;
  *)
    echo "Unexpected yay options; cannot preserve the yay-debug package contract" >&2
    exit 1
    ;;
esac
