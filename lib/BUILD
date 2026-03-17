# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""rules_pkg internal code.

All interfaces are subject to change at any time.
"""

load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(
    default_package_metadata = ["//:license"],
    default_visibility = ["//visibility:public"],
)

filegroup(
    name = "standard_package",
    srcs = [
        "BUILD",
    ] + glob([
        "*.py",
    ]),
    visibility = [
        "//distro:__pkg__",
        "//doc_build:__pkg__",
    ],
)

py_library(
    name = "cpio",
    srcs = [
        "cpio.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "deb_reader",
    srcs = [
        "deb_reader.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "dmg_reader",
    srcs = [
        "dmg_reader.py",
    ],
    deps = [
        ":pkg_reader",
        ":tree_reader",
    ],
)

py_library(
    name = "fs_reader",
    srcs = [
        "fs_reader.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "in_process_pipe",
    srcs = [
        "in_process_pipe.py",
    ],
)

py_library(
    name = "pkg_reader",
    srcs = [
        "pkg_reader.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "rpm_file",
    srcs = [
        "rpm_file.py",
    ],
)

py_library(
    name = "rpm_reader",
    srcs = [
        "rpm_reader.py",
    ],
    deps = [
        ":cpio",
        ":in_process_pipe",
        ":rpm_file",
        ":tree_reader",
    ],
)

py_library(
    name = "saved_tree",
    srcs = [
        "saved_tree.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "tar_reader",
    srcs = [
        "tar_reader.py",
    ],
    deps = [":tree_reader"],
)

py_library(
    name = "tree_reader",
    srcs = [
        "tree_reader.py",
    ],
)

py_test(
    name = "in_process_pipe_test",
    srcs = ["in_process_pipe_test.py"],
    deps = [
        ":deb_reader",
        ":dmg_reader",
        ":fs_reader",
        ":pkg_reader",
        ":rpm_reader",
        ":tar_reader",
        ":tree_reader",
    ],
)
