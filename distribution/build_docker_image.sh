#!/usr/bin/env bash
# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
#
# Builds a docker image from a tar of files (rooted at /), using the
# docker CLI directly, and saves it to the requested output path.
#
# Usage: build_docker_image.sh <docker> <input.tar> <output.docker>
#
# <docker> is the path to the docker CLI, normally supplied from the
# @docker_tools toolchain (see //toolchains/docker:configure.bzl).
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <docker> <input.tar> <output.docker>" >&2
  exit 1
fi

docker="$1"
shift

input_tar="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
output_path="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
image_tag="package-readers:bazel-$$"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"; "$docker" image rm -f "$image_tag" >/dev/null 2>&1 || true' EXIT

cp "$input_tar" "$workdir/distribution.tar"
cat > "$workdir/Dockerfile" <<'EOF'
FROM scratch
ADD distribution.tar /
EOF

"$docker" build --tag "$image_tag" "$workdir" >&2
"$docker" save "$image_tag" -o "$output_path"
