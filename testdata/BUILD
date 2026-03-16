# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Test data for tree_size_compare tests."""

load("@rules_pkg//pkg:deb.bzl", "pkg_deb")
load("@rules_pkg//pkg:mappings.bzl", "pkg_attributes", "pkg_files", "pkg_mkdirs", "pkg_mklink")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

package(
    default_package_metadata = ["//:license"],
    default_visibility = ["//visibility:public"],
)

# Reference tree source files
filegroup(
    name = "reference_files",
    srcs = glob(["reference_tree/**"]),
)

# Package the reference files with explicit attributes for reproducibility
pkg_files(
    name = "reference_pkg_files",
    srcs = [
        "reference_tree/hello.txt",
        "reference_tree/subdir/nested.txt",
    ],
    attributes = pkg_attributes(
        gid = 0,
        mode = "0644",
        uid = 0,
    ),
    strip_prefix = "reference_tree",
)

pkg_mkdirs(
    name = "reference_dirs",
    attributes = pkg_attributes(
        gid = 0,
        mode = "0755",
        uid = 0,
    ),
    dirs = [
        "subdir",
    ],
)

pkg_mklink(
    name = "reference_link",
    link_name = "link_to_hello",
    target = "hello.txt",
)

# Basic tar (uncompressed)
pkg_tar(
    name = "reference_tar",
    srcs = [
        ":reference_dirs",
        ":reference_link",
        ":reference_pkg_files",
    ],
)

# Compressed variants
pkg_tar(
    name = "reference_tar_gz",
    extension = "tar.gz",
    srcs = [
        ":reference_dirs",
        ":reference_link",
        ":reference_pkg_files",
    ],
)

pkg_tar(
    name = "reference_tar_xz",
    extension = "tar.xz",
    srcs = [
        ":reference_dirs",
        ":reference_link",
        ":reference_pkg_files",
    ],
)

# Variant with different file for size comparison tests
pkg_files(
    name = "modified_files",
    srcs = [
        "reference_tree/hello.txt",
    ],
    attributes = pkg_attributes(
        gid = 0,
        mode = "0644",
        uid = 0,
    ),
    strip_prefix = "reference_tree",
)

pkg_tar(
    name = "modified_tar",
    srcs = [
        ":modified_files",
    ],
)

# Variant with different mode for metadata comparison tests
pkg_files(
    name = "different_mode_files",
    srcs = [
        "reference_tree/hello.txt",
        "reference_tree/subdir/nested.txt",
    ],
    attributes = pkg_attributes(
        gid = 0,
        mode = "0755",  # Different from reference (0644)
        uid = 0,
    ),
    strip_prefix = "reference_tree",
)

pkg_tar(
    name = "different_mode_tar",
    srcs = [
        ":reference_dirs",
        ":reference_link",
        ":different_mode_files",
    ],
)

# Variant with different uid/gid for ownership comparison tests
pkg_files(
    name = "different_owner_files",
    srcs = [
        "reference_tree/hello.txt",
        "reference_tree/subdir/nested.txt",
    ],
    attributes = pkg_attributes(
        gid = 1000,
        mode = "0644",
        uid = 1000,
    ),
    strip_prefix = "reference_tree",
)

pkg_tar(
    name = "different_owner_tar",
    srcs = [
        ":reference_dirs",
        ":reference_link",
        ":different_owner_files",
    ],
)

# Variant with different symlink target
pkg_mklink(
    name = "modified_link",
    link_name = "link_to_hello",
    target = "subdir/nested.txt",  # Different target
)

pkg_tar(
    name = "different_symlink_tar",
    srcs = [
        ":reference_dirs",
        ":modified_link",
        ":reference_pkg_files",
    ],
)

# Variant with extra file (for "only in got" test)
pkg_files(
    name = "extra_file",
    srcs = [
        "reference_tree/hello.txt",
    ],
    attributes = pkg_attributes(
        gid = 0,
        mode = "0644",
        uid = 0,
    ),
    prefix = "extra",
    strip_prefix = "reference_tree",
)

pkg_tar(
    name = "extra_file_tar",
    srcs = [
        ":extra_file",
        ":reference_dirs",
        ":reference_link",
        ":reference_pkg_files",
    ],
)

# ============================================================================
# DEB package for testing DebReader
# ============================================================================

genrule(
    name = "generate_deb_files",
    outs = [
        "etc/nsswitch.conf",
        "usr/fizzbuzz",
    ],
    cmd = "for i in $(OUTS); do echo 1 >$$i; done",
)

pkg_mklink(
    name = "java_link",
    link_name = "usr/bin/java",
    target = "/path/to/bin/java",
)

pkg_tar(
    name = "test_deb_data",
    srcs = [
        ":etc/nsswitch.conf",
        ":java_link",
        ":usr/fizzbuzz",
    ],
    extension = "tar.gz",
    mode = "0644",
    modes = {"usr/fizzbuzz": "0755"},
    owner = "0.0",
    package_dir = "/",
    strip_prefix = ".",
)

pkg_deb(
    name = "test_deb",
    data = ":test_deb_data",
    description = "Test package for DebReader",
    maintainer = "test@test.com",
    package = "testpkg",
    version = "1.0",
)
