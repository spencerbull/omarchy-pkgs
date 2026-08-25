#!/bin/bash

set -euo pipefail

url="https://open.spotify.com/"
chromium_args=()
target=""

while (($#)); do
  case $1 in
    --uri=spotify:*|-uri=spotify:*|--uri=https://open.spotify.com/*|-uri=https://open.spotify.com/*)
      target=${1#*=}
      shift
      ;;
    --uri|-uri)
      if [[ ${2:-} == spotify:* || ${2:-} == https://open.spotify.com/* ]]; then
        target=$2
        shift 2
      else
        chromium_args+=("$1")
        shift
      fi
      ;;
    spotify:*|https://open.spotify.com/*)
      target=$1
      shift
      ;;
    *)
      chromium_args+=("$1")
      shift
      ;;
  esac
done

if [[ $target == spotify:* ]]; then
  path=${target#spotify:}
  url="https://open.spotify.com/${path//://}"
elif [[ $target == https://open.spotify.com/* ]]; then
  url=$target
fi

exec chromium --app="$url" "${chromium_args[@]}"
