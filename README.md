# package_readers

This project is a set of tools to read various package formats.
There currently are readers for tar, cpio, ar, rpm, deb, and dmg
formats.  These provide a python API that streams per/file metadata,
expanding sub-archives along the way.  For example, the .deb format
reader streams the content of data.tar.xz rather than just the 3
top level files of a .deb container.

There are some sample tools to compare packages to each other.
Users should expect to build special purpose tools for their particular needs.
