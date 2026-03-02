# package_readers

This project is a set of python tools to read various package formats.
There currently are readers for tar, cpio, ar, rpm, deb, and dmg
formats.  These provide a python API that streams per/file metadata,
expanding sub-archives along the way.  For example, the .deb format
reader streams the content of data.tar.xz rather than just the 3
top level files of a .deb container.

There are some sample tools to compare packages to each other, but
the intent is not to provide only reference/example implementations
of commonly useful things.  Users should expect to build special
purpose tools for their particular needs.

Some of the code here is AI generated. The ar, deb, rpm and cpio readers
were hand crafted by a human.
