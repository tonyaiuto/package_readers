# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Reader for docker image tarballs (output of `docker save`).

A `docker save` tarball contains a manifest.json describing the image,
with an ordered list of layer tar files. Layers are applied in order,
each one overlaying the files of the previous layers (standard OCI/AUFS
overlay semantics): a later layer's file replaces an earlier one at the
same path, and a whiteout marker (a file named ".wh.<name>") deletes
<name> from the merged tree. A directory containing ".wh..wh..opq"
is "opaque": the directory's contents from earlier layers are hidden,
only entries from this layer and later ones are kept.

This reader squashes the layers into that final merged filesystem view
(the same content you'd see inside the running container) and streams
it out as a TreeReader, consistent with how the other readers in this
package expose extracted content rather than raw archive framing.
"""

import json
import tarfile

from lib.tree_reader import FileInfo, TreeReader

WHITEOUT_PREFIX = ".wh."
OPAQUE_WHITEOUT_SUFFIX = ".wh..wh..opq"


class DockerReader(TreeReader):
    """Reader for docker image tarballs (`docker save` output)."""

    def __init__(self, docker_path: str):
        """Initialize DockerReader with path to a docker-save tarball."""
        self.items = []
        self.index = 0
        self._load(docker_path)

    def _load(self, docker_path: str):
        tree = {}
        with tarfile.open(docker_path, mode="r:*") as outer:
            manifest = self._read_manifest(outer)
            for layer_name in manifest["Layers"]:
                self._apply_layer(outer, layer_name, tree)
        self.items = list(tree.values())

    def _read_manifest(self, outer: tarfile.TarFile) -> dict:
        member = outer.extractfile("manifest.json")
        if member is None:
            raise ValueError("manifest.json not found in docker tarball")
        data = json.load(member)
        if not isinstance(data, list) or not data:
            raise ValueError("manifest.json must contain a non-empty array")
        return data[0]

    def _apply_layer(self, outer: tarfile.TarFile, layer_name: str, tree: dict):
        layer_member = outer.extractfile(layer_name)
        if layer_member is None:
            raise ValueError(f"layer {layer_name} not found in docker tarball")
        with tarfile.open(fileobj=layer_member, mode="r|*") as layer:
            for tarinfo in layer:
                self._apply_entry(tarinfo, tree)

    def _apply_entry(self, tarinfo: tarfile.TarInfo, tree: dict):
        name = tarinfo.name.removeprefix("./")
        if not name or name == ".":
            return

        dirname, _, basename = name.rpartition("/")

        if basename == OPAQUE_WHITEOUT_SUFFIX:
            self._remove_subtree(tree, dirname)
            return

        if basename.startswith(WHITEOUT_PREFIX):
            deleted = basename[len(WHITEOUT_PREFIX):]
            deleted_path = f"{dirname}/{deleted}" if dirname else deleted
            self._remove_subtree(tree, deleted_path)
            return

        is_symlink = tarinfo.issym() or tarinfo.islnk()
        is_dir = tarinfo.isdir() and not is_symlink

        tree[name] = FileInfo(
            path=name,
            size=0 if (is_symlink or is_dir) else tarinfo.size,
            mode=tarinfo.mode,
            uid=tarinfo.uid,
            gid=tarinfo.gid,
            is_dir=is_dir,
            is_symlink=is_symlink,
            symlink_target=tarinfo.linkname if is_symlink else None,
        )

    def _remove_subtree(self, tree: dict, path: str):
        """Remove path and everything nested under it from tree."""
        prefix = path + "/"
        for existing in [p for p in tree if p == path or p.startswith(prefix)]:
            del tree[existing]

    def next(self) -> FileInfo:
        """Return the next FileInfo, or None if no more items."""
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        return None

    def is_done(self) -> bool:
        """Return True if all items have been read."""
        return self.index >= len(self.items)
