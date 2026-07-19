"""PyInstaller entry point for UVProTermBT.

PyInstaller freezes this as a standalone script. It imports and runs the
package's main(), so all relative imports inside uvprotermbt/__main__.py
(from . import __version__, from .config import Settings, etc.) work
correctly — PyInstaller preserves package context when modules are imported
as package members, but NOT when __main__.py is frozen directly as the
top-level script.
"""
from uvprotermbt.__main__ import main

if __name__ == "__main__":
    main()
