# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Builds a self-contained distribution of the command line tools, and
packages it both as a .deb and as a docker image (via `docker save`),
built from the exact same tar so they can be used as integration tests
for the readers in //lib: a .deb and a docker image built from identical
input must be read back as identical trees.
"""

load("@rules_pkg//pkg:deb.bzl", "pkg_deb")
load("@rules_pkg//pkg:mappings.bzl", "pkg_attributes", "pkg_files")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")
load("@rules_python//python:py_test.bzl", "py_test")
load(":docker_image.bzl", "docker_image_from_tar")

package(
    default_package_metadata = ["//:license"],
)

# ============================================================================
# Self-contained (single file, `--build_python_zip`-style) executables.
#
# py_binary's implicit ".zip" output is a plain zipapp regardless of build
# flags. Prepending a shebang makes it directly executable, matching what
# `bazel build --build_python_zip` would produce for the default output,
# without depending on that flag.
# ============================================================================

_ZIP_TO_EXE_CMD = "printf '#!/usr/bin/env python3\\n' > $@ && cat $(SRCS) >> $@ && chmod +x $@"

# py_binary's zipapp output is only reachable as the "python_zip_file"
# output group (that's what --build_python_zip builds by default); pull
# it out via a filegroup so the genrules below can depend on it directly.
filegroup(
    name = "tree_size_compare_zip",
    srcs = ["//tools:tree_size_compare"],
    output_group = "python_zip_file",
)

filegroup(
    name = "rpm_info_zip",
    srcs = ["//tools:rpm_info"],
    output_group = "python_zip_file",
)

filegroup(
    name = "cpio_ls_zip",
    srcs = ["//tools:cpio-ls"],
    output_group = "python_zip_file",
)

genrule(
    name = "tree_size_compare_bin",
    srcs = [":tree_size_compare_zip"],
    outs = ["tree_size_compare"],
    cmd = _ZIP_TO_EXE_CMD,
)

genrule(
    name = "rpm_info_bin",
    srcs = [":rpm_info_zip"],
    outs = ["rpm_info"],
    cmd = _ZIP_TO_EXE_CMD,
)

genrule(
    name = "cpio_ls_bin",
    srcs = [":cpio_ls_zip"],
    outs = ["cpio-ls"],
    cmd = _ZIP_TO_EXE_CMD,
)

# ============================================================================
# Package payload: the three tools installed under /usr/bin.
#
# The same tar is used as the .deb data payload and as the docker image
# layer below, so both outputs are built from byte-identical content.
# ============================================================================

pkg_files(
    name = "distribution_files",
    srcs = [
        ":cpio_ls_bin",
        ":rpm_info_bin",
        ":tree_size_compare_bin",
    ],
    attributes = pkg_attributes(
        gid = 0,
        mode = "0755",
        uid = 0,
    ),
    prefix = "/usr/bin",
)

pkg_tar(
    name = "distribution_tar",
    srcs = [":distribution_files"],
)

# ============================================================================
# .deb package
# ============================================================================

pkg_deb(
    name = "package_readers_deb",
    architecture = "all",
    data = ":distribution_tar",
    description = "Command line tools for reading package formats: " +
                   "tree_size_compare, rpm_info, cpio-ls.",
    maintainer = "Tony Aiuto <tony@aiuto.dev>",
    package = "package-readers",
    version = "0.1.0",
)

# ============================================================================
# Docker image, built straight from //tools via the docker CLI (not a
# hermetic bazel rule) per instructions: `FROM scratch` + `ADD` of the same
# tar used for the .deb, then `docker save`.
# ============================================================================

genrule(
    name = "xpackage_readers_docker",
    srcs = [":distribution_tar"],
    outs = ["xpackage_readers.docker"],
    cmd = "$(location build_docker_image.sh) $(SRCS) $@",
    local = True,
    tags = [
        "manual",
        "requires-docker",
    ],
    tools = ["build_docker_image.sh"],
)

# ============================================================================
# Integration test: the .deb and the docker image above are built from the
# same tar, so DebReader and DockerReader must read back identical trees.
# Requires the docker image, so it inherits "manual"/"requires-docker".
# Docker image, built straight from //tools with system docker CLI commands
docker_image_from_tar(
    name = "package_readers_docker",
    src = ":distribution_tar",
    out = "package_readers.docker",
    tags = [
        "requires_docker",
    ],
)

# Integration test: the .deb and the docker image above are built from the
# same tar, so DebReader and DockerReader must read back identical trees.
# ============================================================================

py_test(
    name = "integration_test",
    srcs = ["integration_test.py"],
    data = [
        ":package_readers_deb",
        ":package_readers_docker",
    ],
    tags = [
        "requires_docker",
    ],
    deps = [
        "//tools:tree_size_compare_lib",
        "@rules_python//python/runfiles",
    ],
)
