#!/bin/bash
set -euo pipefail

# Use the runtime prepared by Omarchy rather than a separate CLI on PATH.
export HERMES_DESKTOP_IGNORE_EXISTING=1

# Chromium cannot reliably infer the Secret Service password-store backend
# from a Hyprland session, even when GNOME Keyring is already providing it.
# Keep an explicit user choice (such as KWallet), otherwise select the
# libsecret backend that this package depends on.
export HERMES_DESKTOP_PASSWORD_STORE="${HERMES_DESKTOP_PASSWORD_STORE:-gnome-libsecret}"

# Reconcile every launch rather than trusting whatever installed us. A plain
# `pacman -S hermes-desktop`, or an install interrupted partway, leaves any
# Hermes the terminal agent had built still sitting there, and by then the
# menu entry that would have tidied it up is disabled because we are present.
if command -v omarchy-install-hermes-cli >/dev/null 2>&1; then
  omarchy-install-hermes-cli >/dev/null 2>&1 || true
fi

# Chromium's own Ozone detection falls back to XWayland often enough to matter,
# and the result is a blurry window on every scaled display. Ask for Wayland
# directly, unless the user has already picked a platform themselves.
platform_flags=()
if [[ -n "${WAYLAND_DISPLAY:-}" || ${XDG_SESSION_TYPE:-} == wayland ]]; then
  platform_flags=(--ozone-platform=wayland)

  for flag in "$@"; do
    case "$flag" in
    --ozone-platform=* | --ozone-platform-hint=*) platform_flags=() ;;
    esac
  done
fi

hermes_home=$(realpath -ms -- "${HERMES_HOME:-$HOME/.hermes}")
parent=${hermes_home%/*}
if [[ ${parent##*/} == [Pp][Rr][Oo][Ff][Ii][Ll][Ee][Ss] ]]; then
  hermes_home=${parent%/*}
  hermes_home=${hermes_home:-/}
fi
export HERMES_HOME="$hermes_home"
runtime="$hermes_home/hermes-agent"
native="$runtime/apps/desktop/release/linux-unpacked/Hermes"

if [[ -x $native && -x $runtime/venv/bin/hermes ]]; then
  if (( $# == 0 )); then
    if (( ${#platform_flags[@]} )); then
      export ELECTRON_OZONE_PLATFORM_HINT="${ELECTRON_OZONE_PLATFORM_HINT:-wayland}"
    fi
    exec "$runtime/venv/bin/hermes" desktop --skip-build
  else
    # The upstream CLI does not accept Electron arguments or hermes:// URLs.
    if unshare --user --map-root-user true 2>/dev/null; then
      platform_flags+=(--disable-setuid-sandbox)
    fi
    exec "$native" "${platform_flags[@]}" "$@"
  fi
else
  exec /opt/hermes-desktop/Hermes "${platform_flags[@]}" "$@"
fi
