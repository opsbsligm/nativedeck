#!/usr/bin/env bash
# Fail before publishing an incomplete archive or checksum list.
set -euo pipefail
source_dir=$(realpath -e -- "$1")
archive=$(realpath -m -- "$2")
manifest=$(realpath -m -- "$3")
[[ -d "$source_dir" && ! -e "$archive" && ! -e "$manifest" ]]
mkdir -p "$(dirname "$archive")" "$(dirname "$manifest")"
archive_tmp=$(mktemp "${archive}.partial.XXXXXX")
manifest_tmp=$(mktemp "${manifest}.partial.XXXXXX")
trap 'rm -f -- "$archive_tmp" "$manifest_tmp"' EXIT
(
  cd "$source_dir"
  find . -type f -print0 | sort -z | xargs -0 -r sha256sum > "$manifest_tmp"
  [[ -s "$manifest_tmp" ]]
  sha256sum --quiet -c "$manifest_tmp"
)
tar -C "$(dirname "$source_dir")" --zstd -cf "$archive_tmp" -- "$(basename "$source_dir")"
[[ -s "$archive_tmp" ]]
# Read the archive back; successful compression alone does not prove readability.
tar --zstd -tf "$archive_tmp" > /dev/null
mv -n -- "$manifest_tmp" "$manifest"
mv -n -- "$archive_tmp" "$archive"
[[ ! -e "$manifest_tmp" && ! -e "$archive_tmp" ]]
sha256sum "$archive"
