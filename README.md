# package_readers

This project is a set of python tools to read various package formats.
There currently are readers for tar, cpio, ar, zip, rpm, deb, dmg, pkg,
msi and docker image formats.  These provide a python API that streams
per/file metadata, expanding sub-archives along the way.  For example,
the .deb format reader streams the content of data.tar.xz rather than
just the 3 top level files of a .deb container.

There are some sample tools to compare packages to each other, but
the intent is not to provide only reference/example implementations
of commonly useful things.  Users should expect to build special
purpose tools for their particular needs.

Some of the code here is AI generated. The ar, deb, rpm and cpio readers
were hand crafted by a human.

## Supported inputs

`tools/tree_size_compare` picks a reader based on the file name:

| Input                                   | Reader              |
|-----------------------------------------|---------------------|
| directory                               | `FileSystemReader`  |
| `.json` (saved with `--save`)           | `SavedTreeReader`   |
| `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz` | `TarReader` |
| `.zip`, `.jar`, `.whl`                  | `ZipReader`         |
| `.deb`                                  | `DebReader`         |
| `.rpm`                                  | `RpmReader`         |
| `.dmg`                                  | `DmgReader`         |
| `.pkg` (macOS installer)                | `PkgReader`         |
| `.msi` (Windows Installer)              | `MsiReader`         |
| `.docker` (`docker save` output)        | `DockerReader`      |

Every reader yields the same `FileInfo` records (path, size, mode, uid,
gid, directory/symlink info), so any input can be compared with any other.

## Running the compare tool

With Bazel:

```sh
bazel build //tools:tree_size_compare
bazel-bin/tools/tree_size_compare --help
```

Or straight from a checkout, with no dependencies beyond Python 3:

```sh
python3 -m tools.tree_size_compare --help
```

The examples below use `tree_size_compare` as shorthand for either one.
The tool exits 0 when the trees match and 1 when it finds differences,
so it can be used directly as a CI check.

## Example: save a baseline and compare a new build against it

A common use is guarding a release package against unexpected changes.
Record the file list of a known good build once, check the JSON into your
repo, and compare each new build against it.

Save the baseline:

```sh
$ tree_size_compare --save myapp_baseline.json myapp-1.0.tar.gz
Scanning tree: myapp-1.0.tar.gz
Found 4 items
Saved to myapp_baseline.json
```

The saved file is a sorted, human readable list. uid and gid are left
out when they are 0.

```json
[
  {
    "path": "hello.txt",
    "mode": "644",
    "size": 14
  },
  {
    "path": "link_to_hello",
    "mode": "777",
    "is_symlink": true,
    "target": "hello.txt"
  },
  {
    "path": "subdir",
    "mode": "755",
    "is_dir": true
  },
  {
    "path": "subdir/nested.txt",
    "mode": "644",
    "size": 23
  }
]
```

Later, compare a fresh build against it. The first argument is the
*expected* tree, the second is what you *got*:

```sh
$ tree_size_compare myapp_baseline.json myapp-1.1.tar.gz
Loading expected tree: myapp_baseline.json
Found 4 items
Comparing against: myapp-1.1.tar.gz

Files/directories in got but not in expected:
  [directory] extra
  [file] extra/hello.txt

Files with changed metadata (mode/uid/gid):
  hello.txt: mode 644 -> 755
  subdir/nested.txt: mode 644 -> 755
```

When a change is intended, regenerate the baseline with `--save` and
commit the new JSON along with the change, so the diff shows up in
code review.

The "got" side does not have to be a package. Pointing it at a
directory, such as an install root or an unpacked image, checks what
actually landed on disk:

```sh
tree_size_compare myapp_baseline.json /opt/myapp
```

When either side is a directory, uid/gid comparison is off by default,
because files on disk are usually owned by whoever unpacked them. Use
`--compare_uid_gid` to turn it back on.

## Example: compare across formats

Readers normalize paths (no leading `./`), so the same content packaged
two different ways compares as identical. This is handy for checking that
a `.zip` for one platform and a `.deb` for another ship the same files:

```sh
$ tree_size_compare myapp.zip myapp_1.0_amd64.deb
Loading expected tree: myapp.zip
Found 6 items
Comparing against: myapp_1.0_amd64.deb

Trees are identical.
```

Packages often differ in expected ways, such as a `.deb` holding
`usr/share/doc/` files that the zip does not. Use `--include` and
`--exclude` (regular expressions, can be repeated) to limit the
comparison to the part you care about:

```sh
tree_size_compare --exclude '^usr/share/doc/' myapp.zip myapp_1.0_amd64.deb
tree_size_compare --include '^opt/myapp/' myapp-1.0.tar.gz myapp_1.0_amd64.deb
```

Be aware that modes are not yet normalized across all readers. The tar,
deb, docker, zip and msi readers report permission bits only (`644`),
while the rpm, pkg and dmg readers and directories on disk also include
the file type bits (`100644`). Comparing across those two groups
currently reports a mode change for every entry.

Some formats carry less metadata than others. Zip and MSI have no file
owners, and MSI has no Unix permissions (files are reported as `644`,
directories as `755`). Add `--no-compare_uid_gid` when comparing these
against packages that set owners.

## Example: size thresholds

Size checks catch accidental bloat, such as a debug binary or an
uncompressed asset sneaking into a release. By default a file fails if
it grows more than 1%, and files smaller than 500 bytes are not
size-checked. Tune this with:

```sh
tree_size_compare \
    --max_allowed_percent_increase 5 \
    --max_allowed_absolute_increase 1048576 \
    --minimum_compare_size 4096 \
    --no-show_decreases \
    release_baseline.json myapp-2.0.msi
```

## Using the readers from Python

The tool is a thin layer over the reader API, so it is easy to write your
own checks:

```python
from lib.deb_reader import DebReader

reader = DebReader("myapp_1.0_amd64.deb")
while (info := reader.next()) is not None:
    if not info.is_dir and info.size > 10_000_000:
        print(f"{info.path}: {info.size} bytes")
```

See [tools/README.md](tools/README.md) for the other sample tools.
