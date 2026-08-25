#!/bin/bash

OBSIDIAN_USER_FLAGS_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/obsidian/user-flags.conf"
OBSIDIAN_USER_FLAGS=()

if [[ -f "$OBSIDIAN_USER_FLAGS_FILE" ]]; then
  mapfile -t OBSIDIAN_USER_FLAGS < <(
    sed -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "$OBSIDIAN_USER_FLAGS_FILE"
  )
fi

exec /opt/obsidian/obsidian "${OBSIDIAN_USER_FLAGS[@]}" "$@"
