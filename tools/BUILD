# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Example tools for examining packages.
"""

load("@rules_python//python:py_binary.bzl", "py_binary")

package(
    default_package_metadata = ["//:license"],
    default_visibility = ["//visibility:public"],
)

py_binary(
    name = "cpio-ls",
    srcs = [
        "cpio-ls.py",
    ],
    deps = [
        "//lib:cpio",
    ],
)

py_binary(
    name = "rpm2cpio",
    srcs = [
        "rpm2cpio.py",
    ],
    deps = [
        "//lib:rpm_file",
    ],
)

py_binary(
    name = "tree_size_compare",
    srcs = [
        "tree_size_compare.py",
    ],
    deps = [
        "//lib:deb_reader",
        "//lib:dmg_reader",
        "//lib:fs_reader",
        "//lib:rpm_reader",
        "//lib:saved_tree",
        "//lib:tar_reader",
        "//lib:tree_reader",
    ],
)
