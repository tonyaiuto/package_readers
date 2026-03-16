# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Example tools for examining packages.
"""

load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")

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
    name = "rpm_info",
    srcs = [
        "rpm_info.py",
    ],
    deps = [
        "//lib:cpio",
        "//lib:in_process_pipe",
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

py_library(
    name = "tree_size_compare_lib",
    srcs = ["tree_size_compare.py"],
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

 
py_test(
    name = "readers_test",
    srcs = ["readers_test.py"],
    data = [
        "//testdata:reference_tar",
        "//testdata:reference_tar_gz",
        "//testdata:reference_tar_xz",
        "//testdata:test_deb",
    ],
    deps = [
        "//lib:deb_reader",
        "//lib:in_process_pipe",
        "//lib:saved_tree",
        "//lib:tar_reader",
        "@rules_python//python/runfiles",
    ],
)
 
py_test(
    name = "compare_test",
    srcs = ["compare_test.py"],
    data = [
        "//testdata:different_mode_tar",
        "//testdata:different_owner_tar",
        "//testdata:different_symlink_tar",
        "//testdata:extra_file_tar",
        "//testdata:modified_tar",
        "//testdata:reference_tar",
    ],
    deps = [
        ":tree_size_compare_lib",
        "@rules_python//python/runfiles",
    ],
)
