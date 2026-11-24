# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Pure Python reader for Windows Installer (.msi) packages.

An .msi file is an OLE Compound File (CFB) holding a small relational
database. The installed file layout is described by three tables:

  Directory  (Directory, Directory_Parent, DefaultDir)
  Component  (Component, Directory_, ...)
  File       (File, Component_, FileName, FileSize, ...)

This reader parses just enough of the database to walk those tables and
stream a FileInfo for each directory and file that would be installed.
File contents (in embedded or external .cab files) are not read; sizes
come from the File table.

The MSI database decoding (stream name encoding, string pool, column
type bits, column-major row layout) is adapted from pymsi
(https://github.com/nightlark/pymsi), Copyright (c) 2022, Lawrence
Livermore National Security, LLC, MIT License; see
third_party_licenses/pymsi.txt. pymsi uses olefile for
the CFB container; this module has a minimal CFB reader instead so that
it depends on the stdlib only.

MSI has no Unix permissions or owners, so files are reported with mode
0o644 and directories with 0o755, and uid/gid are 0.

Paths: TARGETDIR is the root. Well-known system folders (e.g.
ProgramFilesFolder) are resolved at install time, so they appear as
their property name, e.g. "ProgramFilesFolder/Acme/app.exe".
"""

import struct

from lib.tree_reader import FileInfo, TreeReader

FILE_MODE = 0o644
DIR_MODE = 0o755

# ============================================================================
# Compound File Binary (CFB / OLE2) container
# ============================================================================

CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
MAXREGSECT = 0xFFFFFFFA
ENDOFCHAIN = 0xFFFFFFFE
NOSTREAM = 0xFFFFFFFF

_DIR_ENTRY_SIZE = 128
_TYPE_STREAM = 2
_TYPE_ROOT = 5


class CompoundFile:
    """Minimal read-only CFB parser: enough to read top level streams."""

    def __init__(self, data: bytes):
        if len(data) < 512 or data[:8] != CFB_MAGIC:
            raise ValueError("Not an OLE compound file (bad magic)")
        self._data = data
        (sector_shift, mini_shift) = struct.unpack_from("<HH", data, 0x1E)
        self._sector_size = 1 << sector_shift
        self._mini_sector_size = 1 << mini_shift
        (
            num_fat_sectors,
            first_dir_sector,
            _txn,
            self._mini_cutoff,
            first_minifat_sector,
            _num_minifat,
            first_difat_sector,
            num_difat_sectors,
        ) = struct.unpack_from("<IIIIIIII", data, 0x2C)

        self._fat = self._load_fat(num_fat_sectors, first_difat_sector, num_difat_sectors)
        self._entries = self._load_directory(first_dir_sector)
        root = self._entries[0]
        if root["type"] != _TYPE_ROOT:
            raise ValueError("CFB directory has no root entry")
        self._mini_stream = self._read_chain(root["start"], root["size"])
        if first_minifat_sector <= MAXREGSECT:
            raw = self._read_chain(first_minifat_sector)
            self._minifat = list(struct.unpack_from(f"<{len(raw) // 4}I", raw))
        else:
            self._minifat = []
        self._streams = self._collect_streams(root["child"])

    def _sector(self, sector: int) -> bytes:
        offset = (sector + 1) * self._sector_size
        # The final sector may be short in truncated-but-valid files.
        if offset >= len(self._data):
            raise ValueError(f"CFB sector {sector} is past end of file")
        return self._data[offset : offset + self._sector_size]

    def _load_fat(self, num_fat_sectors, first_difat_sector, num_difat_sectors):
        difat = list(struct.unpack_from("<109I", self._data, 0x4C))
        per_sector = self._sector_size // 4
        sector = first_difat_sector
        for _ in range(num_difat_sectors):
            if sector > MAXREGSECT:
                break
            entries = struct.unpack_from(f"<{per_sector}I", self._sector(sector))
            difat.extend(entries[:-1])
            sector = entries[-1]
        fat = []
        for s in difat[:num_fat_sectors]:
            if s > MAXREGSECT:
                continue
            fat.extend(struct.unpack_from(f"<{per_sector}I", self._sector(s)))
        return fat

    def _chain(self, start: int, table: list):
        seen = set()
        sector = start
        while sector <= MAXREGSECT:
            if sector in seen or sector >= len(table):
                raise ValueError("Corrupt CFB sector chain")
            seen.add(sector)
            yield sector
            sector = table[sector]

    def _read_chain(self, start: int, size: int = None) -> bytes:
        data = b"".join(self._sector(s) for s in self._chain(start, self._fat))
        return data if size is None else data[:size]

    def _read_mini_chain(self, start: int, size: int) -> bytes:
        mss = self._mini_sector_size
        data = b"".join(
            self._mini_stream[s * mss : (s + 1) * mss]
            for s in self._chain(start, self._minifat)
        )
        return data[:size]

    def _load_directory(self, first_dir_sector: int) -> list:
        raw = self._read_chain(first_dir_sector)
        entries = []
        for off in range(0, len(raw) - _DIR_ENTRY_SIZE + 1, _DIR_ENTRY_SIZE):
            name_len = struct.unpack_from("<H", raw, off + 0x40)[0]
            name = raw[off : off + max(0, name_len - 2)].decode("utf-16-le", "replace")
            etype = raw[off + 0x42]
            left, right, child = struct.unpack_from("<III", raw, off + 0x44)
            start, size = struct.unpack_from("<IQ", raw, off + 0x74)
            if self._sector_size == 512:
                # Version 3 files: high 32 bits of size are undefined.
                size &= 0xFFFFFFFF
            entries.append(
                {
                    "name": name,
                    "type": etype,
                    "left": left,
                    "right": right,
                    "child": child,
                    "start": start,
                    "size": size,
                }
            )
        return entries

    def _collect_streams(self, top: int) -> dict:
        """Walk the root storage's red-black tree, returning {name: entry}."""
        streams = {}
        todo = [top]
        seen = set()
        while todo:
            idx = todo.pop()
            if idx == NOSTREAM or idx in seen or idx >= len(self._entries):
                continue
            seen.add(idx)
            entry = self._entries[idx]
            todo.append(entry["left"])
            todo.append(entry["right"])
            if entry["type"] == _TYPE_STREAM:
                streams[entry["name"]] = entry
        return streams

    def exists(self, name: str) -> bool:
        return name in self._streams

    def read_stream(self, name: str) -> bytes:
        entry = self._streams.get(name)
        if entry is None:
            raise KeyError(f"No such stream: {name!r}")
        if entry["size"] < self._mini_cutoff:
            return self._read_mini_chain(entry["start"], entry["size"])
        return self._read_chain(entry["start"], entry["size"])


# ============================================================================
# MSI database (adapted from pymsi)
# ============================================================================

TABLE_PREFIX = "䡀"

COL_FIELD_SIZE_MASK = 0xFF
COL_VALID_BIT = 0x100
COL_STRING_BIT = 0x800
COL_NULLABLE_BIT = 0x1000
LONG_STRING_REFS_BIT = 0x80000000

# Code pages that MSI string pools commonly declare. 0 means "neutral".
_CODEPAGES = {
    932: "cp932",
    936: "gbk",
    949: "cp949",
    950: "cp950",
    951: "cp950",
    1250: "cp1250",
    1251: "cp1251",
    1252: "cp1252",
    1253: "cp1253",
    1254: "cp1254",
    1255: "cp1255",
    1256: "cp1256",
    1257: "cp1257",
    1258: "cp1258",
    10000: "mac_roman",
    10007: "mac_cyrillic",
    20127: "ascii",
    28591: "latin_1",
    28592: "iso8859_2",
    28593: "iso8859_3",
    28594: "iso8859_4",
    28595: "iso8859_5",
    28596: "iso8859_6",
    28597: "iso8859_7",
    28598: "iso8859_8",
    65000: "utf-7",
    65001: "utf-8",
}


def _utf2mime(x: int):
    if ord("0") <= x <= ord("9"):
        return x - ord("0")
    if ord("A") <= x <= ord("Z"):
        return x - ord("A") + 10
    if ord("a") <= x <= ord("z"):
        return x - ord("a") + 36
    if x == ord("."):
        return 62
    if x == ord("_"):
        return 63
    return None


def encode_stream_name(name: str, is_table: bool = False) -> str:
    """Encode an MSI logical stream name into its CFB stream name.

    MSI packs pairs of [0-9A-Za-z._] characters into single code points
    in U+3800..U+47FF so that names fit CFB's 31 character limit.
    """
    out = TABLE_PREFIX if is_table else ""
    i = 0
    while i < len(name):
        v1 = _utf2mime(ord(name[i]))
        if v1 is None:
            out += name[i]
            i += 1
            continue
        if i + 1 < len(name):
            v2 = _utf2mime(ord(name[i + 1]))
            if v2 is not None:
                out += chr(0x3800 + (v2 << 6) + v1)
                i += 2
                continue
        out += chr(0x4800 + v1)
        i += 1
    return out


class StringPool:
    """The MSI string table (_StringPool + _StringData streams)."""

    def __init__(self, pool: bytes, data: bytes):
        (codepage,) = struct.unpack_from("<I", pool, 0)
        self.long_refs = bool(codepage & LONG_STRING_REFS_BIT)
        codepage &= ~LONG_STRING_REFS_BIT
        self._encoding = _CODEPAGES.get(codepage)
        self.strings = []
        pos, dpos = 4, 0
        while pos + 4 <= len(pool):
            length, refcount = struct.unpack_from("<HH", pool, pos)
            pos += 4
            if length == 0 and refcount > 0:
                # Long string: real length in the next entry slot.
                (length,) = struct.unpack_from("<I", pool, pos)
                pos += 4
            self.strings.append(self._decode(data[dpos : dpos + length]))
            dpos += length

    def _decode(self, raw: bytes) -> str:
        if self._encoding:
            return raw.decode(self._encoding, "replace")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp1252", "replace")

    def ref_width(self) -> int:
        return 3 if self.long_refs else 2

    def lookup(self, ref: int):
        if ref == 0:
            return None
        if ref - 1 >= len(self.strings):
            raise ValueError(f"String reference {ref} out of range")
        return self.strings[ref - 1]


class _Column:
    """A column's storage type, decoded from its _Columns type bits."""

    def __init__(self, name: str, kind: str):
        self.name = name
        self.kind = kind  # "str", "i16", "i32", or "binary"

    @classmethod
    def from_bits(cls, name: str, bits: int) -> "_Column":
        if (bits & ~COL_NULLABLE_BIT) == (COL_STRING_BIT | COL_VALID_BIT):
            return cls(name, "binary")
        if bits & COL_STRING_BIT:
            return cls(name, "str")
        size = bits & COL_FIELD_SIZE_MASK
        if size == 4:
            return cls(name, "i32")
        if size in (1, 2):
            return cls(name, "i16")
        raise ValueError(f"Invalid MSI column field size {size} for {name}")

    def width(self, pool: StringPool) -> int:
        if self.kind == "str":
            return pool.ref_width()
        return 4 if self.kind == "i32" else 2


def _read_rows(data: bytes, columns: list, pool: StringPool) -> list:
    """Decode a table stream. Tables are stored column-major."""
    row_size = sum(c.width(pool) for c in columns)
    if row_size == 0 or not data:
        return []
    if len(data) % row_size != 0:
        raise ValueError("MSI table data length is not a multiple of row size")
    nrows = len(data) // row_size
    rows = [dict() for _ in range(nrows)]
    pos = 0
    for col in columns:
        for row in rows:
            if col.kind == "str":
                ref = struct.unpack_from("<H", data, pos)[0]
                if pool.long_refs:
                    ref |= data[pos + 2] << 16
                value = pool.lookup(ref)
            elif col.kind == "i32":
                v = struct.unpack_from("<i", data, pos)[0]
                value = None if v == 0 else v ^ -0x80000000
            elif col.kind == "i16":
                v = struct.unpack_from("<h", data, pos)[0]
                value = None if v == 0 else v ^ -0x8000
            else:  # binary: data lives in a separate stream
                value = None
            pos += col.width(pool)
            row[col.name] = value
    return rows


# Bootstrap schema for the _Columns table itself.
_COLUMNS_SCHEMA = [
    _Column("Table", "str"),
    _Column("Number", "i16"),
    _Column("Name", "str"),
    _Column("Type", "i16"),
]


class MsiDatabase:
    """Read-only access to the tables of an MSI package."""

    def __init__(self, data: bytes):
        self._cfb = CompoundFile(data)
        self._pool = StringPool(
            self._cfb.read_stream(encode_stream_name("_StringPool", True)),
            self._cfb.read_stream(encode_stream_name("_StringData", True)),
        )
        self._schema = self._load_schema()

    def _load_schema(self) -> dict:
        raw = self._cfb.read_stream(encode_stream_name("_Columns", True))
        cols = {}
        for row in _read_rows(raw, _COLUMNS_SCHEMA, self._pool):
            cols.setdefault(row["Table"], []).append((row["Number"], row["Name"], row["Type"]))
        return {
            table: [_Column.from_bits(name, bits) for _, name, bits in sorted(entries)]
            for table, entries in cols.items()
        }

    def has_table(self, name: str) -> bool:
        return name in self._schema

    def rows(self, name: str) -> list:
        """Return the rows of table `name` as a list of dicts."""
        if name not in self._schema:
            return []
        stream = encode_stream_name(name, True)
        if not self._cfb.exists(stream):
            return []
        return _read_rows(self._cfb.read_stream(stream), self._schema[name], self._pool)


# ============================================================================
# TreeReader
# ============================================================================

# Directory ids that Windows Installer resolves to system locations.
SYSTEM_FOLDERS = frozenset(
    [
        "AdminToolsFolder",
        "AppDataFolder",
        "CommonAppDataFolder",
        "CommonFiles64Folder",
        "CommonFilesFolder",
        "DesktopFolder",
        "FavoritesFolder",
        "FontsFolder",
        "LocalAppDataFolder",
        "MyPicturesFolder",
        "NetHoodFolder",
        "PersonalFolder",
        "PrintHoodFolder",
        "ProgramFiles64Folder",
        "ProgramFilesFolder",
        "ProgramMenuFolder",
        "RecentFolder",
        "SendToFolder",
        "StartMenuFolder",
        "StartupFolder",
        "System16Folder",
        "System64Folder",
        "SystemFolder",
        "TempFolder",
        "TemplateFolder",
        "WindowsFolder",
        "WindowsVolume",
    ]
)


def _long_name(name: str) -> str:
    """Pick the long name from MSI "short|long" filename syntax."""
    return name.split("|", 1)[1] if "|" in name else name


def _target_dir_name(default_dir: str) -> str:
    """Return the install-time name component of a DefaultDir value.

    DefaultDir is "target[:source]", and each half may be "short|long".
    A target of "." means "same as the parent directory".
    """
    target = (default_dir or ".").split(":", 1)[0]
    name = _long_name(target)
    return "" if name == "." else name


class MsiReader(TreeReader):
    """Reader for Windows Installer .msi packages."""

    def __init__(self, msi_path: str):
        with open(msi_path, "rb") as f:
            db = MsiDatabase(f.read())
        self._items = self._build_tree(db)
        self._index = 0

    @staticmethod
    def _build_tree(db: MsiDatabase) -> list:
        directories = {row["Directory"]: row for row in db.rows("Directory")}
        dir_paths = {}

        def dir_path(dir_id: str) -> str:
            if dir_id in dir_paths:
                return dir_paths[dir_id]
            # Walk up to the root iteratively, guarding against cycles.
            chain = []
            cur = dir_id
            while cur is not None and cur not in dir_paths:
                if cur in chain:
                    raise ValueError(f"Cycle in MSI Directory table at {cur}")
                chain.append(cur)
                row = directories.get(cur)
                parent = row["Directory_Parent"] if row else None
                cur = None if parent == cur else parent
            base = dir_paths.get(cur, "") if cur is not None else ""
            for d in reversed(chain):
                row = directories.get(d)
                parent = row["Directory_Parent"] if row else None
                if row is None or parent is None or parent == d:
                    part = ""  # TARGETDIR (or another root)
                elif d in SYSTEM_FOLDERS:
                    part = d
                else:
                    part = _target_dir_name(row["DefaultDir"])
                base = f"{base}/{part}" if base and part else (base or part)
                dir_paths[d] = base
            return dir_paths[dir_id]

        component_dirs = {
            row["Component"]: row["Directory_"] for row in db.rows("Component")
        }

        items = {}

        def add_dir(path: str):
            while path and path not in items:
                items[path] = FileInfo(path=path, size=0, mode=DIR_MODE, is_dir=True)
                path = path.rpartition("/")[0]

        for dir_id in set(component_dirs.values()):
            add_dir(dir_path(dir_id))

        for row in db.rows("File"):
            dir_id = component_dirs.get(row["Component_"])
            if dir_id is None:
                raise ValueError(
                    f"MSI File {row['File']} references unknown component {row['Component_']}"
                )
            parent = dir_path(dir_id)
            name = _long_name(row["FileName"])
            path = f"{parent}/{name}" if parent else name
            items[path] = FileInfo(path=path, size=row["FileSize"] or 0, mode=FILE_MODE)

        return [items[p] for p in sorted(items)]

    def next(self) -> FileInfo:
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        return None

    def is_done(self) -> bool:
        return self._index >= len(self._items)
