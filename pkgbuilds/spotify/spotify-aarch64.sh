#!/bin/bash

set -euo pipefail

url="https://open.spotify.com/"

if [[ ${1:-} == spotify:* ]]; then
  path=${1#spotify:}
  url="https://open.spotify.com/${path//://}"
  shift
elif [[ ${1:-} == https://open.spotify.com/* ]]; then
  url=$1
  shift
fi

exec chromium --app="$url" "$@"
