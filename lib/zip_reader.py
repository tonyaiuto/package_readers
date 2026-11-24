# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Zip file reader."""

import stat
import zipfile

from lib.tree_reader import FileInfo, TreeReader

# zipfile create_system value for archives made on Unix.
_UNIX = 3

DEFAULT_FILE_MODE = 0o644
DEFAULT_DIR_MODE = 0o755


class ZipReader(TreeReader):
    """Reader for .zip archives (also .jar, .whl, etc.).

    Modes are reported as permission bits only (no file type bits), to
    match TarReader. Zip archives built on non-Unix systems carry no
    permissions, so they get DEFAULT_FILE_MODE / DEFAULT_DIR_MODE. Zip has
    no notion of owner, so uid and gid are always 0.
    """

    def __init__(self, zip_path: str):
        self._zip = zipfile.ZipFile(zip_path, "r")
        self._iter = iter(self._zip.infolist())
        self.done = False

    def next(self) -> FileInfo:
        if self.done:
            return None
        while True:
            try:
                zinfo = next(self._iter)
            except StopIteration:
                self.done = True
                self._zip.close()
                return None
            path = zinfo.filename.removeprefix("./").rstrip("/")
            if path and path != ".":
                break

        unix_mode = zinfo.external_attr >> 16 if zinfo.create_system == _UNIX else 0
        is_symlink = stat.S_ISLNK(unix_mode)
        is_dir = not is_symlink and (zinfo.is_dir() or stat.S_ISDIR(unix_mode))

        perms = stat.S_IMODE(unix_mode)
        if not perms:
            perms = DEFAULT_DIR_MODE if is_dir else DEFAULT_FILE_MODE

        target = None
        if is_symlink:
            # The symlink target is stored as the entry's content.
            target = self._zip.read(zinfo).decode("utf-8")

        return FileInfo(
            path=path,
            size=0 if (is_dir or is_symlink) else zinfo.file_size,
            mode=perms,
            is_dir=is_dir,
            is_symlink=is_symlink,
            symlink_target=target,
        )

    def is_done(self) -> bool:
        return self.done
