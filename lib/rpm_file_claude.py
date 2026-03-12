# Copyright 2026 Tony Aiuto
#
# See LICENSE.txt
"""Archive reader library for .rpm file testing.

Skips rpm file headers, and the provides the cpio format stream.

Gleaned from: http://ftp.rpm.org/max-rpm/s1-rpm-file-format-rpm-file-format.html.
"""

from collections import namedtuple
import bz2
import json
import lzma
import sys
import zlib

DEBUG = 0

RpmLead = namedtuple(
    "RpmLead", "magic, major, minor, type, arch, name, os, signature_type"
)

RpmSectionInfo = namedtuple(
    "RpmSectionInfo", "start, end, n_entries, data_len, padding"
)

RPM_MAGIC = b"\xed\xab\xee\xdb"
RPM_TYPE_BINARY = 0
RPM_TYPE_SOURCE = 1

# This is probably YAGNI
RPM_ARCH_X86 = 1
RPM_ARCH_ALPHA = 2
RPM_ARCH_SPARC = 3
RPM_ARCH_MIPS = 4
RPM_ARCH_PPC = 5
RPM_ARCH_68K = 6
RPM_ARCH_SGI = 7

ARCH_2_S = {
    RPM_ARCH_X86: "x86",
    RPM_ARCH_ALPHA: "alpha",
    RPM_ARCH_SPARC: "sparc",
    RPM_ARCH_MIPS: "mips",
    RPM_ARCH_PPC: "ppc",
    RPM_ARCH_68K: "680000",
    RPM_ARCH_SGI: "sgi",
}

RPM_HEADER_MAGIC = b"\x8e\xad\xe8"
HEADER_INDEX_ENTRY_SIZE = 16

HEADER_NULL = 0
HEADER_CHAR = 1
HEADER_INT8 = 2
HEADER_INT16 = 3
HEADER_INT32 = 4
HEADER_INT64 = 5
HEADER_STRING = 6
HEADER_BIN = 7
HEADER_STRING_ARRAY = 8

# Some interesting tags.
RPMTAG_SUMMARY = 1004
RPMTAG_DESCRIPTION = 1005
RPMTAG_BUILDTIME = 1006
RPMTAG_BUILDHOST = 1007
RPMTAG_INSTALLTIME = 1008
RPMTAG_SIZE = 1009
RPMTAG_DISTRIBUTION = 1010
RPMTAG_VENDOR = 1011
RPMTAG_LICENSE = 1014
RPMTAG_OS = 1021
RPMTAG_ARCH = 1022
RPMTAG_PAYLOADCOMPRESSOR = 1125


def _read_network_byte(stream):
    return int.from_bytes(stream.read(1), byteorder="big")


def _read_network_short(stream):
    return int.from_bytes(stream.read(2), byteorder="big")


def _read_network_long(stream):
    return int.from_bytes(stream.read(4), byteorder="big")


def _read_string(stream, max_len):
    """Read an ASCIZ string."""
    buf = stream.read(max_len)
    for i in range(max_len):
        if buf[i] == 0:
            return buf[0:i].decode("utf-8")
    return buf.decode("utf-8")


def _get_int32(buf, pos):
    return int.from_bytes(buf[pos : pos + 4], byteorder="big")


def _get_n_ints(buf, offset, count, width):
    if count == 1:
        return int.from_bytes(buf[offset : offset + width], byteorder="big")
    ret = []
    for i in range(count):
        pos = offset + i * width
        ret.append(int.from_bytes(buf[pos : pos + width], byteorder="big"))
    return ret


def _get_null_terminated_string(buf, pos):
    ret = []
    while True:
        c = buf[pos]
        pos += 1
        if c == 0:
            return bytes(ret).decode("utf-8")
        ret.append(c)


class RpmFileReader(object):
    """Read and analyze RPM files.

    This class can read RPM files, parse headers, and stream the CPIO payload.
    It also tracks byte positions for structure analysis.
    """

    BLOCKSIZE = 65536

    def __init__(self, stream, verbose=False):
        self.stream = stream
        self.verbose = verbose
        self.compression = None  # compression of cpio payload
        self.have_read_headers = False

        # Structure info populated during read_headers()
        self.lead = None
        self.lead_start = 0
        self.lead_end = 0
        self.sig_info = None
        self.header_info = None
        self.payload_start = 0
        self.payload_compression = None
        self.headers = None  # Parsed header tags
        self._payload_prefix = b""  # Bytes read for compression detection
        self._header_bytes = None  # Buffered header bytes (if requested)

    def log(self, s):
        if self.verbose:
            print(s, file=sys.stderr)

    def _get_rpm_lead(self):
        """Get the legacy lead header."""
        magic = self.stream.read(4)
        major = _read_network_byte(self.stream)
        minor = _read_network_byte(self.stream)
        type = _read_network_short(self.stream)
        arch = _read_network_short(self.stream)
        name = _read_string(self.stream, 66)
        os = _read_network_short(self.stream)
        signature_type = _read_network_short(self.stream)
        _ = self.stream.read(16)
        return RpmLead(
            magic=magic,
            major=major,
            minor=minor,
            type=type,
            arch=arch,
            name=name,
            os=os,
            signature_type=signature_type,
        )

    def _read_header_start(self):
        """The start of the header is 16 bytes long."""
        magic = self.stream.read(3)
        if magic != RPM_HEADER_MAGIC:
            raise ValueError(
                f"expected header magic '{RPM_HEADER_MAGIC}', got '{magic}'"
            )
        version = _read_network_byte(self.stream)
        if version != 1:
            raise ValueError(f"expected header version '1', got '{version}'")
        _ = self.stream.read(4)  # skip reserved bytes
        n_entries = _read_network_long(self.stream)
        data_len = _read_network_long(self.stream)
        return n_entries, data_len

    def _get_rpm_signature(self):
        """Read the signature header section.

        Returns:
            RpmSectionInfo with byte positions and entry counts.
        """
        start = self.stream.tell()
        n_entries, data_len = self._read_header_start()
        headers = []
        for i in range(n_entries):
            tag = _read_network_long(self.stream)
            type = _read_network_long(self.stream)
            offset = _read_network_long(self.stream)
            count = _read_network_long(self.stream)
            headers.append((tag, type, offset, count))
        data_store = self.stream.read(data_len)

        for header in headers:
            tag, type, offset, count = header
            if DEBUG > 1:
                print(f"sig header: {tag}, {type}, {offset} {count}", file=sys.stderr)
            if tag == 1000:  # SIGTAG_SIZE
                # TODO: Report errors better.
                assert type == HEADER_INT32
                assert count == 1
                file_size = _get_int32(data_store, offset)
                if self.verbose:
                    self.log(f"Signature: file size: {file_size}")
            if DEBUG > 1:
                if type == HEADER_STRING:
                    print(
                        "  STRING:",
                        _get_null_terminated_string(data_store, offset),
                        file=sys.stderr,
                    )
                if type == HEADER_STRING_ARRAY:
                    for i in range(count):
                        s = _get_null_terminated_string(data_store, offset)
                        # print("  STRING:", i, s, file=sys.stderr)
                        offset += len(s) + 1

        # Signature section is padded to 8-byte boundary
        sig_total = 16 + (n_entries * 16) + data_len
        padding = (8 - (sig_total % 8)) % 8
        if padding:
            self.stream.read(padding)

        end = self.stream.tell()
        return RpmSectionInfo(
            start=start,
            end=end,
            n_entries=n_entries,
            data_len=data_len,
            padding=padding,
        )

    def _get_headers(self):
        """Read the main header section.

        Returns:
            tuple: (headers_dict, RpmSectionInfo)
        """
        start = self.stream.tell()
        n_entries, data_len = self._read_header_start()
        headers = []
        for i in range(n_entries):
            tag = _read_network_long(self.stream)
            type = _read_network_long(self.stream)
            offset = _read_network_long(self.stream)
            count = _read_network_long(self.stream)
            headers.append((tag, type, offset, count))
        data_store = self.stream.read(data_len)
        ret = {}
        for header in headers:
            tag, type, offset, count = header
            if DEBUG > 1:
                print(f"header: {tag}, {type}, {offset} {count}", file=sys.stderr)

            # In verbose mode we print some generally interesting values.
            if tag == RPMTAG_PAYLOADCOMPRESSOR:
                self.compression = _get_null_terminated_string(data_store, offset)
                self.log(f"Compression: {self.compression}")
            if tag == RPMTAG_ARCH:
                self.log(f"arch: {_get_null_terminated_string(data_store, offset)}")
            if tag == RPMTAG_BUILDHOST:
                self.log(
                    f"build_host: {_get_null_terminated_string(data_store, offset)}"
                )
            if tag == RPMTAG_DESCRIPTION:
                self.log(
                    f"description: {_get_null_terminated_string(data_store, offset)}"
                )
            if tag == RPMTAG_DISTRIBUTION:
                self.log(
                    f"distribution: {_get_null_terminated_string(data_store, offset)}"
                )
            if tag == RPMTAG_LICENSE:
                self.log(f"license: {_get_null_terminated_string(data_store, offset)}")
            if tag == RPMTAG_OS:
                self.log(f"os: {_get_null_terminated_string(data_store, offset)}")
            if tag == RPMTAG_SUMMARY:
                self.log(f"summary: {_get_null_terminated_string(data_store, offset)}")
            if tag == RPMTAG_VENDOR:
                self.log(f"vendor: {_get_null_terminated_string(data_store, offset)}")
            if DEBUG > 1 and type == HEADER_STRING:
                print(
                    "  STRING:",
                    _get_null_terminated_string(data_store, offset),
                    file=sys.stderr,
                )

            # Save the headers in a dict so we can serialize to JSON.
            if type == HEADER_INT16:
                ret[tag] = _get_n_ints(data_store, offset, count, 2)

            elif type == HEADER_INT32:
                ret[tag] = _get_n_ints(data_store, offset, count, 4)

            elif type == HEADER_INT64:
                ret[tag] = _get_n_ints(data_store, offset, count, 8)

            elif type == HEADER_STRING:
                ret[tag] = _get_null_terminated_string(data_store, offset)

            elif type == HEADER_STRING_ARRAY:
                values = []
                for i in range(count):
                    s = _get_null_terminated_string(data_store, offset)
                    # print("  STRING:", i, s, file=sys.stderr)
                    values.append(s)
                    offset += len(s) + 1
                ret[tag] = values

        end = self.stream.tell()
        section_info = RpmSectionInfo(
            start=start,
            end=end,
            n_entries=n_entries,
            data_len=data_len,
            padding=0,  # Main header has no padding
        )
        return ret, section_info

    def read_headers(self, headers_out=None):
        """Read the initial part of the RPM file to get the headers.

        After calling this, the following attributes are populated:
        - lead: RpmLead namedtuple
        - lead_start, lead_end: byte positions
        - sig_info: RpmSectionInfo for signature section
        - header_info: RpmSectionInfo for main header
        - headers: dict of parsed header tags
        - payload_start: byte offset where payload begins
        - payload_compression: detected compression type
        - compression: compression from header tag (may differ from detected)
        """
        self.lead_start = self.stream.tell()
        lead = self._get_rpm_lead()
        self.lead = lead
        self.lead_end = self.stream.tell()

        if DEBUG > 1:
            print(lead, file=sys.stderr)
        if lead.magic != RPM_MAGIC:
            raise ValueError(f"expected magic '{RPM_MAGIC}', got '{lead.magic}'")
        if lead.major != 3:
            raise ValueError(f"Can not handle RPM version '{lead.major}.{lead.minor}'")
        if lead.signature_type != 5:
            raise ValueError(f"Unexpected signature type '{lead.signature_type}'")

        self.sig_info = self._get_rpm_signature()
        headers, self.header_info = self._get_headers()
        self.headers = headers

        # Record payload start position
        self.payload_start = self.stream.tell()

        # Detect payload compression from magic bytes
        # Save these bytes to prepend when streaming (no seeking)
        self._payload_prefix = self.stream.read(6)
        self.payload_compression = self._detect_compression(self._payload_prefix)

        if headers_out:
            with open(headers_out, "w") as out:
                json.dump(headers, indent=2, fp=out)
        self.have_read_headers = True

    def _detect_compression(self, magic):
        """Detect compression type from magic bytes."""
        if magic[:2] == b'\x1f\x8b':
            return "gzip"
        elif magic[:6] == b'\xfd7zXZ\x00':
            return "xz"
        elif magic[:3] == b'BZh':
            return "bzip2"
        elif magic[:4] == b'\x28\xb5\x2f\xfd':
            return "zstd"
        elif magic[:6] == b'070701' or magic[:6] == b'070702':
            return "none"
        else:
            return "unknown"

    def get_payload_size(self, file_size=None):
        """Get the payload size in bytes.

        Args:
            file_size: Total file size. If not provided, attempts to seek
                       to determine size (only works with seekable streams).

        Returns:
            Payload size in bytes.

        Must call read_headers() first.
        """
        if not self.have_read_headers:
            raise IOError("Must call read_headers() first")
        if file_size is not None:
            return file_size - self.payload_start
        # Try to determine size by seeking (only works with seekable streams)
        if not self.stream.seekable():
            raise IOError("Cannot determine payload size: stream is not seekable and file_size not provided")
        pos = self.stream.tell()
        self.stream.seek(0, 2)  # Seek to end
        total_size = self.stream.tell()
        self.stream.seek(pos)  # Restore position
        return total_size - self.payload_start

    def extract_header_bytes(self):
        """Extract the raw header bytes (lead + signature + header).

        Returns everything before the payload.
        Must call read_headers() first.

        Note: Only works with seekable streams. For non-seekable streams,
        use buffer_header_bytes=True when calling read_headers().
        """
        if not self.have_read_headers:
            raise IOError("Must call read_headers() first")
        if self._header_bytes is not None:
            return self._header_bytes
        if not self.stream.seekable():
            raise IOError("Cannot extract header bytes: stream is not seekable")
        pos = self.stream.tell()
        self.stream.seek(0)
        header_bytes = self.stream.read(self.payload_start)
        self.stream.seek(pos)
        return header_bytes

    def stream_cpio(self, out_stream):
        """Decompress and stream the CPIO payload.

        Note: This consumes the stream. The stream position after read_headers()
        is 6 bytes into the payload (from compression detection). Those bytes
        are buffered and prepended automatically.
        """
        if not self.have_read_headers:
            raise IOError("Called stream_cpio before calling read_headers.")

        # Use detected compression if header-specified compression is not set
        compression = self.compression or self.payload_compression

        # We have 6 bytes already read for compression detection
        prefix = self._payload_prefix

        if not compression or compression == "none":
            # Write the prefix bytes first
            out_stream.write(prefix)
            while True:
                block = self.stream.read(128 * 1024)
                if not block:
                    break
                out_stream.write(block)

        elif compression == "lzma" or compression == "xz":
            decompressor = lzma.LZMADecompressor()
            # Decompress the prefix bytes first
            out_stream.write(decompressor.decompress(prefix))
            while not decompressor.eof:
                block = self.stream.read(RpmFileReader.BLOCKSIZE)
                if not block:
                    break
                out_stream.write(decompressor.decompress(block))
            # If not at EOF, the input data was incomplete or corrupted.
            if not decompressor.eof and not decompressor.needs_input:
                raise IOError(
                    "Compressed data ended before the end-of-stream marker was reached"
                )

        elif compression == "gzip":
            # Use wbits=31 (MAX_WBITS | 16) to handle gzip format
            decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
            # Decompress the prefix bytes first
            out_stream.write(decompressor.decompress(prefix))
            while not decompressor.eof:
                block = self.stream.read(RpmFileReader.BLOCKSIZE)
                if not block:
                    break
                out_stream.write(decompressor.decompress(block))
            if not decompressor.eof:
                raise IOError(
                    "gzip data ended before the end-of-stream marker was reached"
                )

        elif compression == "bzip2":
            decompressor = bz2.BZ2Decompressor()
            # Decompress the prefix bytes first
            out_stream.write(decompressor.decompress(prefix))
            while not decompressor.eof:
                block = self.stream.read(RpmFileReader.BLOCKSIZE)
                if not block:
                    break
                out_stream.write(decompressor.decompress(block))
            # If not at EOF, the input data was incomplete or corrupted.
            if not decompressor.eof and not decompressor.needs_input:
                raise IOError(
                    "Compressed data ended before the end-of-stream marker was reached"
                )

        # TODO: zstd
        out_stream.close()
