#!/usr/bin/env bash
set -euo pipefail

conf_path="${1:-nginx/default.conf}"

if [[ ! -e "$conf_path" ]]; then
  echo "Missing required nginx config: $conf_path" >&2
  exit 1
fi

if [[ -d "$conf_path" ]]; then
  echo "Invalid nginx config path: $conf_path is a directory, but Docker expects a file." >&2
  exit 1
fi

if [[ ! -f "$conf_path" ]]; then
  echo "Invalid nginx config path: $conf_path exists but is not a regular file." >&2
  exit 1
fi
