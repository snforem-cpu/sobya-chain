#!/usr/bin/env bash
set -euo pipefail

# Run from repository root after building the approved sobyad binary.
# This helper packages only the binary; it never creates or publishes a release.
: "${SOBYA_VERSION:?Set SOBYA_VERSION to the approved version/tag}"
: "${SOBYA_BINARY:=dist/sobyad}"

if [[ ! -f "$SOBYA_BINARY" ]]; then
  echo "Missing binary: $SOBYA_BINARY" >&2
  exit 1
fi
mkdir -p dist
output="$(pwd)/dist/sobyad-${SOBYA_VERSION}-linux-amd64.tar.gz"
binary_dir="$(cd "$(dirname "$SOBYA_BINARY")" && pwd)"
binary_name="$(basename "$SOBYA_BINARY")"
tar -C "$binary_dir" -czf "$output" "$binary_name"
(
  cd dist
  sha256sum "sobyad-${SOBYA_VERSION}-linux-amd64.tar.gz" > SHA256SUMS
  sha256sum -c SHA256SUMS
)
echo "Package and SHA256SUMS created in dist/. This script does not publish a release."
