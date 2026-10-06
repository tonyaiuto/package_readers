# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Tests for DockerReader."""

import io
import json
import tarfile
import tempfile
import unittest

from lib.docker_reader import DockerReader


def _layer_tar_bytes(entries: list) -> bytes:
    """Build an in-memory tar for one layer.

    Each entry is a dict with keys: name, and one of:
      - content: bytes -> regular file
      - is_dir: True -> directory
      - linkname: str -> symlink
    Optional "mode" (default 0o644 for files, 0o755 for dirs).
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for entry in entries:
            info = tarfile.TarInfo(name=entry["name"])
            if entry.get("is_dir"):
                info.type = tarfile.DIRTYPE
                info.mode = entry.get("mode", 0o755)
                tar.addfile(info)
            elif "linkname" in entry:
                info.type = tarfile.SYMTYPE
                info.linkname = entry["linkname"]
                info.mode = entry.get("mode", 0o777)
                tar.addfile(info)
            else:
                content = entry["content"]
                info.size = len(content)
                info.mode = entry.get("mode", 0o644)
                tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _build_docker_tar(layers: list) -> bytes:
    """Build an in-memory docker-save tarball.

    layers: list of (layer_name, entries) in application order.
    """
    manifest = [{
        "Config": "sha256:deadbeef",
        "RepoTags": ["example:latest"],
        "Layers": [name for name, _ in layers],
    }]

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as outer:
        for name, entries in layers:
            layer_bytes = _layer_tar_bytes(entries)
            info = tarfile.TarInfo(name=name)
            info.size = len(layer_bytes)
            outer.addfile(info, io.BytesIO(layer_bytes))

        manifest_bytes = json.dumps(manifest).encode("utf-8")
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        outer.addfile(info, io.BytesIO(manifest_bytes))
    return buf.getvalue()


def _write_temp_docker_tar(layers: list) -> str:
    data = _build_docker_tar(layers)
    f = tempfile.NamedTemporaryFile(suffix=".docker", delete=False)
    f.write(data)
    f.close()
    return f.name


def _load_tree_as_dict(reader) -> dict:
    result = {}
    while True:
        item = reader.next()
        if item is None:
            break
        result[item.path] = item
    return result


class DockerReaderTest(unittest.TestCase):

    def test_single_layer_basic_files(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "etc", "is_dir": True},
                {"name": "etc/app.conf", "content": b"hello"},
                {"name": "bin", "is_dir": True},
                {"name": "bin/link", "linkname": "/usr/bin/real"},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))

        self.assertIn("etc/app.conf", tree)
        self.assertEqual(tree["etc/app.conf"].size, 5)
        self.assertFalse(tree["etc/app.conf"].is_dir)

        self.assertIn("etc", tree)
        self.assertTrue(tree["etc"].is_dir)

        self.assertIn("bin/link", tree)
        self.assertTrue(tree["bin/link"].is_symlink)
        self.assertEqual(tree["bin/link"].symlink_target, "/usr/bin/real")

    def test_paths_have_no_dot_slash_prefix(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "./a.txt", "content": b"x"},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))
        for p in tree:
            self.assertFalse(p.startswith("./"))
        self.assertIn("a.txt", tree)

    def test_later_layer_overwrites_earlier_file(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "app/version.txt", "content": b"old-content", "mode": 0o644},
            ]),
            ("layer2.tar", [
                {"name": "app/version.txt", "content": b"newer", "mode": 0o755},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))

        self.assertEqual(tree["app/version.txt"].size, 5)
        self.assertEqual(tree["app/version.txt"].mode & 0o777, 0o755)

    def test_whiteout_deletes_file_from_earlier_layer(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "app", "is_dir": True},
                {"name": "app/keep.txt", "content": b"keep"},
                {"name": "app/gone.txt", "content": b"gone"},
            ]),
            ("layer2.tar", [
                {"name": "app/.wh.gone.txt", "content": b""},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))

        self.assertIn("app/keep.txt", tree)
        self.assertNotIn("app/gone.txt", tree)
        self.assertNotIn("app/.wh.gone.txt", tree)

    def test_whiteout_deletes_directory_subtree(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "app", "is_dir": True},
                {"name": "app/olddir", "is_dir": True},
                {"name": "app/olddir/a.txt", "content": b"a"},
                {"name": "app/olddir/b.txt", "content": b"b"},
            ]),
            ("layer2.tar", [
                {"name": "app/.wh.olddir", "content": b""},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))

        self.assertNotIn("app/olddir", tree)
        self.assertNotIn("app/olddir/a.txt", tree)
        self.assertNotIn("app/olddir/b.txt", tree)

    def test_opaque_whiteout_hides_earlier_directory_contents(self):
        path = _write_temp_docker_tar([
            ("layer1.tar", [
                {"name": "app", "is_dir": True},
                {"name": "app/sub", "is_dir": True},
                {"name": "app/sub/old1.txt", "content": b"old1"},
                {"name": "app/sub/old2.txt", "content": b"old2"},
            ]),
            ("layer2.tar", [
                {"name": "app/sub/.wh..wh..opq", "content": b""},
                {"name": "app/sub/new.txt", "content": b"new"},
            ]),
        ])
        tree = _load_tree_as_dict(DockerReader(path))

        self.assertNotIn("app/sub/old1.txt", tree)
        self.assertNotIn("app/sub/old2.txt", tree)
        self.assertIn("app/sub/new.txt", tree)
        self.assertIn("app", tree)

    def test_gzip_compressed_layer(self):
        entries = [{"name": "a.txt", "content": b"gzipped"}]
        layer_bytes = _layer_tar_bytes(entries)
        import gzip
        gz = gzip.compress(layer_bytes)

        manifest = [{
            "Config": "sha256:deadbeef",
            "RepoTags": ["example:latest"],
            "Layers": ["layer1.tar.gz"],
        }]
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as outer:
            info = tarfile.TarInfo(name="layer1.tar.gz")
            info.size = len(gz)
            outer.addfile(info, io.BytesIO(gz))

            manifest_bytes = json.dumps(manifest).encode("utf-8")
            info = tarfile.TarInfo(name="manifest.json")
            info.size = len(manifest_bytes)
            outer.addfile(info, io.BytesIO(manifest_bytes))

        f = tempfile.NamedTemporaryFile(suffix=".docker", delete=False)
        f.write(buf.getvalue())
        f.close()

        tree = _load_tree_as_dict(DockerReader(f.name))
        self.assertIn("a.txt", tree)
        self.assertEqual(tree["a.txt"].size, 7)


if __name__ == "__main__":
    unittest.main()
