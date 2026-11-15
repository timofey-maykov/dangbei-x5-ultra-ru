"""Console entry point for the standalone release (no system Python needed)."""
import os
import sys

import install


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if os.name == 'nt' and getattr(sys, 'frozen', False):
        # ADB must load its own DLLs, not the Python bundle's libraries.
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    code = install.run_cli()
    if len(sys.argv) == 1 and sys.stdin.isatty():
        try:
            input('\nНажмите Enter, чтобы закрыть окно...')
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == '__main__':
    sys.exit(main())
