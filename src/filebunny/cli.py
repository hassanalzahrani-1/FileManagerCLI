"""
filebunny CLI entry point.

This module defines the top-level argument parser, prints the branded banner
for help/subshell sessions, and routes subcommands to the `FileManager`.

Design principles:
- Outside the subshell (normal shell), commands operate relative to the caller's CWD.
- Inside the subshell ("burrow"), commands operate relative to the persisted spot.
- The subshell provides lightweight PowerShell/bash helpers that forward args to
  `filebunny` while preserving argparse help behavior.
- Nested subshells are disallowed to avoid confusing prompts and state.
"""

import argparse
from importlib.metadata import version as pkg_version
from filebunny import __version__ as FB_VERSION
import logging
import sys
import os
import subprocess
import platform
import tempfile
import textwrap
from pathlib import Path
from datetime import datetime
from filebunny.manager import FileManager
from filebunny.storage import Storage

# Shared banner (ASCII bunny + quick guide).
# Shown for top-level `filebunny -h` and at subshell startup. The version line
# is injected dynamically above the "Core Commands" heading.
HEADER_BUNNY = textwrap.dedent("""
⠀⠀⠀⠀⠀⠀⠀⠀⣠⣤⣦⣤⣄⡀⠀⠀⠀⠀⢀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣰⠟⠙⠀⠀⠀⠈⢻⡆⠀⣴⠞⠋⠉⠉⠙⠳⣦⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢸⡛⠂⠀⠀⠀⠀⠀⠈⣿⣾⠋⠀⠀⠀⠀⠀⠀⠈⣿⡄⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣽⠁⠀⠀⠀⠀⠀⠀⠀⣽⢇⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢰⣿⠄⠀⠀⠀⠀⠀⠀⠐⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⢺⡇⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢨⡟⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠇⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠈⣿⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⢠⡿⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣿⡆⠀⠀⢀⣀⣀⡀⢸⣇⠀⠀⠀⠀⠀⠀⠀⢀⣾⠃⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣘⡟⠰⠛⠛⠉⠙⠉⠈⠃⠀⠀⠀⠀⠀⠀⢰⣾⡟⠚⢶⣄⠀⠀⠀⠀⠀
⠀⠀⠀⣤⡾⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⡁⠀⢀⡬⢹⡇⠀⠀⠀⠀
⠀⠀⣴⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣷⠀⠚⢷⣼⡷⠀⠀⠀⠀
⠀⣼⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢙⣷⠀⠀⠘⢿⣷⠀⠀⠀
⢸⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣇⠀⠀⠀⢹⣧⠀⠀
⣿⢣⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⡏⣡⠀⠀⠀⠻⣧⠀
⣿⡾⡿⠖⠀⠀⠀⠀⠀⠀⠀⠀⢀⣶⣿⣤⠀⠀⠀⠀⠀⠀⠀⣼⡇⠃⠀⠀⠀⠀⢹⣇
⠹⣧⡀⠀⠀⠰⣦⣸⣶⠄⠀⠀⠸⡿⠿⠇⠀⠀⠀⠀⠀⠀⢢⡿⠅⠀⠀⠀⠀⠀⠀⣿
⠀⠈⠻⣦⣒⠸⠛⠻⠖⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⠟⠁⠀⠀⠀⠀⣄⠀⠀⣾
⠀⠀⠀⠈⢙⣷⢶⣤⣀⣀⠀⠀⠀⠀⠀⠀⠀⣀⣤⡶⠟⠁⠀⠀⠀⠀⠀⣼⢏⣠⣾⠟
⠀⠀⠀⢀⣾⠃⠀⠀⠉⠛⠛⠻⠶⠶⠶⠶⠞⠋⠁⠀⠀⠀⠀⠀⠀⣰⡾⠛⠛⠉⠀⠀
⠀⠀⠀⠘⣿⠀⠀⠀⠀⠀⢲⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⣠⡾⠏⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠻⣧⡀⠀⠀⣡⣿⠛⠻⠶⣾⠀⠀⠀⠀⠀⠀⠈⢾⡟⠆⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠉⠛⠛⠛⠋⠁⠀⠀⠀⢿⣦⠀⠀⠀⠀⠀⣠⡾⠁⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣶⣤⣀⣦⣴⡟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀
Core Commands
-------------
- spot                Show your current spot (absolute path).
- hop [path]          Hop to a directory (updates the bunny spot). Prints the resolved path.
- peek [-al]          List contents (PowerShell-style). Use -al to include dotfiles.
- dig <dir>           Dig a new burrow (mkdir -p).
- carrot <file>       Plant a carrot (create/touch a file; parents auto-created).
- copy <src> <dst>    Copy file/folder.
- move <src> <dst>    Move file/folder.
- rename <src> <dst>  Rename file/folder.
- bury <path>         Bury (delete) file/folder.

Tips
----
- Help: filebunny -h  |  filebunny <command> -h
""")

def main():
    """Main CLI entry point.

    Responsibilities:
    - Build the argparse tree and register global flags (e.g., `-v/--version`).
    - Print the ASCII banner for top-level help without a subcommand.
    - Launch an interactive subshell (PowerShell/bash) when no subcommand is
      provided, with helpers bound for convenience.
    - Disallow nested subshells via `FILEBUNNY_BURROW`.
    - For direct subcommands, operate relative to the caller's current working
      directory (CWD), not the persisted spot.
    """
    parser = argparse.ArgumentParser(prog="filebunny", description="Hop/Spot File Manager")
    sub = parser.add_subparsers(dest="cmd", required=False)

    # spot command - show current directory
    p_spot = sub.add_parser("spot", help="Show current directory")
    p_hop = sub.add_parser("hop", help="Change directory")
    p_hop.add_argument("path", nargs="?", help="Path to hop to (default: home)")

    # peek command - list directory contents
    p_peek = sub.add_parser("peek", help="List directory contents")
    p_peek.add_argument("-al", "--all", action="store_true", help="Show all entries including dot-prefixed (hidden)")

    # copy command - copy files/directories
    p_copy = sub.add_parser("copy", help="Copy file or directory")
    p_copy.add_argument("src", help="Source path")
    p_copy.add_argument("dst", help="Destination path")

    # move command - move files/directories
    p_move = sub.add_parser("move", help="Move file or directory")
    p_move.add_argument("src", help="Source path")
    p_move.add_argument("dst", help="Destination path")

    # bury command - delete files/directories
    p_delete = sub.add_parser("bury", help="Delete file or directory")
    p_delete.add_argument("path", help="Path to bury (delete)")

    # rename command - rename files/directories
    p_rename = sub.add_parser("rename", help="Rename file or directory")
    p_rename.add_argument("src", help="Current name")
    p_rename.add_argument("dst", help="New name")

    # dig (mkdir) and carrot (touch)
    p_dig = sub.add_parser("dig", help="Create a directory (mkdir -p)")
    p_dig.add_argument("path", help="Directory path to create")
    p_carrot = sub.add_parser("carrot", help="Create a file (touch)")
    p_carrot.add_argument("path", help="File path to create")

    # Compute version early and register -v/--version before building banners.
    # Prefer runtime package __version__, fall back to installed metadata.
    _ver = FB_VERSION if FB_VERSION else None
    if not _ver:
        try:
            _ver = pkg_version("filebunny")
        except Exception:
            _ver = "unknown"
    parser.add_argument("-v", "--version", action="version", version=f"filebunny {_ver}")
    # Verbose flag (-V/--verbose) enables INFO logs for this run/session
    parser.add_argument("-V", "--verbose", action="store_true", help="Enable verbose logging for this run/session")

    # If user requested top-level help (-h/--help) without a subcommand,
    # print the banner and exit immediately.

    argv = sys.argv[1:]
    top_level_help = any(flag in argv for flag in ("-h", "--help"))
    verbose_requested = any(flag in argv for flag in ("-V", "--verbose"))
    subcommands = {"spot","hop","peek","copy","move","bury","rename","dig","carrot"}
    mentions_sub = any(token in subcommands for token in argv)
    # Prepare banner with version injected above 'Core Commands'.
    banner = HEADER_BUNNY
    try:
        banner = HEADER_BUNNY.replace("Core Commands", f"filebunny {_ver}\n\nCore Commands")
    except Exception:
        pass
    if top_level_help and not mentions_sub:
        print(banner)
        return

    args = parser.parse_args()
    verbose = bool(getattr(args, "verbose", False) or verbose_requested)
    # Honor FILEBUNNY_LOG_LEVEL for this process (helps tests and direct runs)
    _lvl = os.environ.get("FILEBUNNY_LOG_LEVEL")
    if _lvl:
        try:
            logging.getLogger().setLevel(getattr(logging, _lvl.upper(), logging.INFO))
        except Exception:
            logging.getLogger().setLevel(logging.INFO)
    if getattr(args, "cmd", None) is None:
        # Disallow nested subshells (prevents confusing double prompts/state).
        if os.environ.get("FILEBUNNY_BURROW") == "1":
            print("Already inside a filebunny burrow. Use 'leave' to exit.")
            return
        # Auto-enter burrow subshell immediately.
        fm = FileManager(Storage())
        try:
            dest = fm.spot()
            if platform.system() == "Windows":
                # PowerShell helpers: forward all remaining arguments to the
                # real `filebunny` subcommands so argparse `-h/--help` works.
                # `hop` only changes directory when a valid path is returned.
                ps_function = textwrap.dedent(
                    """
                    function global:spot {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        if ($Args -and $Args.Count -gt 0) {
                            filebunny spot @Args
                            return
                        }
                        $dest = (filebunny spot)
                        if ($LASTEXITCODE -eq 0 -and $dest) { Write-Output $dest }
                    }
                    function global:hop {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        # If asking for help, just forward and return (avoid Set-Location)
                        if ($Args -and ($Args -contains '-h' -or $Args -contains '--help')) {
                            filebunny hop @Args
                            return
                        }
                        $dest = (filebunny hop @Args)
                        if ($LASTEXITCODE -ne 0) { return }
                        # Normalize and validate the returned path before attempting to cd
                        if ($null -ne $dest) { $dest = $dest | Select-Object -First 1 }
                        if ($dest) { $dest = $dest.Trim() }
                        if ($dest -and (Test-Path -LiteralPath $dest)) { Set-Location -LiteralPath $dest }
                    }
                    function global:peek {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny peek @Args
                    }
                    function global:dig {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny dig @Args
                    }
                    function global:carrot {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny carrot @Args
                    }
                    function global:copy {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny copy @Args
                    }
                    function global:move {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny move @Args
                    }
                    function global:bury {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny bury @Args
                    }
                    function global:rename {
                        param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
                        filebunny rename @Args
                    }
                    # Simple white prompt for this burrow session
                    function global:prompt {
                        Write-Host "₍ᐢ. .ᐢ₎ $(Get-Location) > " -NoNewline
                        return ' '
                    }
                    """
                ).strip()
                # Add a 'leave' helper. With -d, revert persisted spot to origin
                # before exiting this subshell session.
                ps_function = ps_function + textwrap.dedent(
                    """
                    function leave {
                        param([switch]$d)
                        if ($d) { $null = filebunny hop $env:FILEBUNNY_ORIGIN }
                        exit
                    }
                    """
                )
                # Build optional verbose export for PowerShell outside of f-string expression
                verbose_ps = "$env:FILEBUNNY_LOG_LEVEL='INFO'; " if verbose else ""
                ps_command = (
                    f"$env:FILEBUNNY_ORIGIN=\"{dest}\"; $env:FILEBUNNY_BURROW='1'; "
                    f"{verbose_ps}"
                    f"{ps_function}; "
                    "Remove-Item alias:copy -ErrorAction SilentlyContinue; "
                    "Remove-Item alias:move -ErrorAction SilentlyContinue; "
                    "Remove-Item alias:rename -ErrorAction SilentlyContinue; "
                    f"Write-Host @'\n{banner}\n'@; Set-Location -LiteralPath \"{dest}\""
                )
                subprocess.run(["powershell", "-NoExit", "-Command", ps_command], check=True)
            else:
                shell = os.environ.get("SHELL") or "/bin/sh"
                if shell.endswith("bash"):
                    # Bash helpers: similar forwarding behavior; `leave -d`
                    # restores the origin spot prior to exiting.
                    rc = textwrap.dedent(
                        """
                        # Remember the origin spot for this burrow session
                        export FILEBUNNY_ORIGIN="${ORIGIN}"
                        # Mark that we're inside a filebunny burrow to prevent nesting
                        export FILEBUNNY_BURROW=1
                        # If verbose requested, enable logging only for this subshell session
                        ${VERBOSE_EXPORT}
                        spot() {
                          filebunny spot
                        }
                        hop() {
                          local dest
                          if [ $# -gt 0 ]; then
                            dest="$(filebunny hop "$1")"
                          else
                            dest="$(filebunny hop)"
                          fi
                          if [ -n "$dest" ] && [ -d "$dest" ]; then
                            cd "$dest"
                          fi
                        }
                        peek() {
                          filebunny peek "$@"
                        }
                        dig() {
                          if [ $# -lt 1 ]; then echo "usage: dig DIR" >&2; return 1; fi
                          filebunny dig "$1"
                        }
                        carrot() {
                          if [ $# -lt 1 ]; then echo "usage: carrot FILE" >&2; return 1; fi
                          filebunny carrot "$1"
                        }
                        copy() {
                          if [ $# -lt 2 ]; then echo "usage: copy SRC DST" >&2; return 1; fi
                          filebunny copy "$1" "$2"
                        }
                        move() {
                          if [ $# -lt 2 ]; then echo "usage: move SRC DST" >&2; return 1; fi
                          filebunny move "$1" "$2"
                        }
                        bury() {
                          if [ $# -lt 1 ]; then echo "usage: bury PATH" >&2; return 1; fi
                          filebunny bury "$1"
                        }
                        rename() {
                          if [ $# -lt 2 ]; then echo "usage: rename SRC DST" >&2; return 1; fi
                          filebunny rename "$1" "$2"
                        }
                        # leave [-d|--discard]: exit subshell; if discard is set, revert persisted spot to origin
                        leave() {
                          if [ "$1" = "-d" ]; then
                            filebunny hop "$FILEBUNNY_ORIGIN" >/dev/null
                          fi
                          builtin exit
                        }
                        # Print shared header, then simple white prompt for this burrow session
                        echo "${HEADER}"  # placeholder, replaced below by Python
                        # Simple white prompt for this burrow session
                        PS1='₍ᐢ. .ᐢ₎ \w > '
                        """
                    )
                    rc = rc.replace("${HEADER}", banner)
                    rc = rc.replace("${ORIGIN}", dest)
                    rc = rc.replace("${VERBOSE_EXPORT}", ("export FILEBUNNY_LOG_LEVEL=INFO" if verbose else "# verbosity off"))
                    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".rc") as tf:
                        tf.write(rc)
                        rc_path = tf.name
                    try:
                        subprocess.run([shell, "--rcfile", rc_path, "-i"], cwd=dest, check=True)
                    finally:
                        try:
                            os.unlink(rc_path)
                        except OSError:
                            pass
                else:
                    subprocess.run([shell, "-i"], cwd=dest, check=True)
        except Exception as e:
            sys.stderr.write(f"burrow error: {e}\n")
            raise SystemExit(1)
        return
    fm = FileManager(Storage())
    # For direct subcommands (not auto-burrow), operate relative to the caller's
    # current working directory (CWD), not the persisted spot.
    fm.cwd = Path.cwd()
    # If -V was provided for a direct command, elevate to INFO for decorators
    if verbose:
        logging.getLogger().setLevel(logging.INFO)

    match args.cmd:
        case "spot": 
            try:
                print(fm.spot())
            except Exception as e:
                sys.stderr.write(f"spot error: {e}\n")
                raise SystemExit(1)
        case "hop": 
            try:
                print(fm.hop(args.path))
            except Exception as e:
                sys.stderr.write(f"hop error: {e}\n")
                raise SystemExit(1)
        case "peek": 
            # Build a long listing from the current spot
            root = Path(fm.spot())
            paths = sorted(root.iterdir(), key=lambda p: (0 if p.is_dir() else 1, p.name.lower()))
            if not getattr(args, "all", False):
                paths = [p for p in paths if not p.name.startswith('.')]

            # Header
            print() ; print()
            print(f"Dig: {root}")
            print()
            print(f"{'Mode':<6}  {'LastWriteTime':<22}  {'Length':>10} {'Name'}")
            print(f"{'-'*4:<6}  {'-'*13:<22}  {'-'*6:>10} {'-'*4}")

            def fmt_time(ts: float) -> str:
                dt = datetime.fromtimestamp(ts)
                # Build like 9/28/2025  10:11 AM (no leading zeros in m/d, two spaces before time)
                m = dt.month
                d = dt.day
                Y = dt.year
                h = dt.hour % 12 or 12
                minute = dt.minute
                ampm = 'AM' if dt.hour < 12 else 'PM'
                return f"{m}/{d}/{Y}  {h}:{minute:02d} {ampm}"

            for p in paths:
                try:
                    st = p.stat()
                    mode = 'd-----' if p.is_dir() else '-a----'
                    when = fmt_time(st.st_mtime)
                    length = '' if p.is_dir() else str(st.st_size)
                    print(f"{mode:<6}  {when:<22}  {length:>10} {p.name}")
                except OSError as e:
                    # On error stat'ing an entry, show minimal info
                    sys.stderr.write(f"peek error: {p.name}: {e}\n")
            print() ; print()
        case "copy": 
            fm.copy(args.src, args.dst)
            print(f"Copied {args.src} to {args.dst}")
        case "move": 
            fm.move(args.src, args.dst)
            print(f"Moved {args.src} to {args.dst}")
        case "bury": 
            fm.delete(args.path)
            print(f"Buried {args.path}")
        case "rename": 
            fm.rename(args.src, args.dst)
            print(f"Renamed {args.src} to {args.dst}")
        case "dig":
            try:
                logging.getLogger().setLevel(logging.WARNING)
                print(fm.dig(args.path))
            except Exception as e:
                sys.stderr.write(f"dig error: {e}\n")
                raise SystemExit(1)
        case "carrot":
            try:
                logging.getLogger().setLevel(logging.WARNING)
                print(fm.carrot(args.path))
            except Exception as e:
                sys.stderr.write(f"carrot error: {e}\n")
                raise SystemExit(1)
