import os
import sys
import logging
from pathlib import Path
import pytest
from contextlib import contextmanager

import filebunny.cli as cli
from filebunny import __version__ as FB_VERSION


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Ensure tests run in normal shell mode with quiet warnings."""
    monkeypatch.delenv("FILEBUNNY_BURROW", raising=False)
    monkeypatch.delenv("FILEBUNNY_LOG_LEVEL", raising=False)
    monkeypatch.delenv("FILEBUNNY_VERBOSE", raising=False)
    monkeypatch.setenv("PYTHONWARNINGS", "ignore")
    yield


@contextmanager
def cwd(path: Path):
    """Temporarily chdir to path and restore previous CWD (prevents Windows hangs)."""
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def test_top_level_help_prints_header(monkeypatch, capsys):
    """filebunny -h should print the immutable header and exit."""
    monkeypatch.setattr(sys, "argv", ["filebunny", "-h"])
    cli.main()
    out = capsys.readouterr().out
    assert "Core Commands" in out
    assert "filebunny <command> -h" in out
    # Version should appear above Core Commands in banner
    assert f"filebunny {FB_VERSION}" in out


def test_spot_prints_cwd_in_normal_shell(tmp_path: Path, monkeypatch, capsys):
    """In normal shell, spot should print the caller's CWD."""
    with cwd(tmp_path):
        monkeypatch.setattr(sys, "argv", ["filebunny", "spot"])  
        cli.main()
        out = capsys.readouterr().out.strip()
        assert os.path.samefile(out, str(tmp_path))


def test_hop_invalid_path_exits_nonzero(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        monkeypatch.setattr(sys, "argv", ["filebunny", "hop", "no_such_dir"])  
        with pytest.raises(SystemExit) as ex:
            cli.main()
        assert ex.value.code == 1
        err = capsys.readouterr().err
        assert "hop error:" in err


def test_peek_hides_dot_by_default(tmp_path: Path, monkeypatch, capsys):
    """peek lists the CWD and hides dot-prefixed entries by default."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x")
    with cwd(tmp_path):
        monkeypatch.setattr(sys, "argv", ["filebunny", "peek"])  
        cli.main()
        out = capsys.readouterr().out
        assert "file.txt" in out
        assert ".hidden" not in out


def test_peek_all_shows_dot(tmp_path: Path, monkeypatch, capsys):
    """peek -al includes dot-prefixed entries in the CWD."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x")
    with cwd(tmp_path):
        monkeypatch.setattr(sys, "argv", ["filebunny", "peek", "-al"])  
        cli.main()
        out = capsys.readouterr().out
        assert ".hidden" in out
        assert "file.txt" in out


def test_peek_help(monkeypatch, capsys):
    """peek -h should show usage and the -al/--all flag."""
    monkeypatch.setattr(sys, "argv", ["filebunny", "peek", "-h"])  
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "usage: filebunny peek" in out
    assert "-al, --all" in out


def test_hop_help(monkeypatch, capsys):
    """hop -h should show usage for hop subcommand."""
    monkeypatch.setattr(sys, "argv", ["filebunny", "hop", "-h"])  
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out
    assert "usage: filebunny hop" in out


def test_top_level_version_flag(monkeypatch, capsys):
    """filebunny --version should print package version and exit."""
    monkeypatch.setattr(sys, "argv", ["filebunny", "--version"])  
    with pytest.raises(SystemExit):
        cli.main()
    out = capsys.readouterr().out.strip()
    assert out.endswith(FB_VERSION)


def test_prevent_nested_subshell(monkeypatch, capsys):
    """When FILEBUNNY_BURROW=1, invoking without subcommand should not launch subshell."""
    monkeypatch.setenv("FILEBUNNY_BURROW", "1")
    monkeypatch.setattr(sys, "argv", ["filebunny"])  
    # Should return cleanly without raising, printing a notice
    cli.main()
    out = capsys.readouterr().out
    assert "Already inside a filebunny burrow" in out


def test_dig_creates_directory(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        target = tmp_path / "new_dir" / "nested"
        monkeypatch.setattr(sys, "argv", ["filebunny", "dig", str(target)])
        cli.main()
        out = capsys.readouterr().out.strip()
        assert target.is_dir()
        # dig prints the created directory path
        assert out.endswith(str(target))


def test_carrot_creates_file(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        target = tmp_path / "a" / "b" / "note.txt"
        monkeypatch.setattr(sys, "argv", ["filebunny", "carrot", str(target)])
        cli.main()
        out = capsys.readouterr().out.strip()
        assert target.is_file()
        assert out.endswith(str(target))


def test_copy_file(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        src = tmp_path / "file.txt"
        dst = tmp_path / "file-copy.txt"
        src.write_text("x")
        monkeypatch.setattr(sys, "argv", ["filebunny", "copy", str(src), str(dst)])
        cli.main()
        out = capsys.readouterr().out
        assert dst.is_file()
        assert dst.read_text() == "x"
        assert "Copied" in out


def test_move_file(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        src = tmp_path / "move.txt"
        dst = tmp_path / "moved.txt"
        src.write_text("y")
        monkeypatch.setattr(sys, "argv", ["filebunny", "move", str(src), str(dst)])
        cli.main()
        out = capsys.readouterr().out
        assert not src.exists()
        assert dst.is_file() and dst.read_text() == "y"
        assert "Moved" in out


def test_rename_file(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        src = tmp_path / "ren.txt"
        dst = tmp_path / "renamed.txt"
        src.write_text("z")
        monkeypatch.setattr(sys, "argv", ["filebunny", "rename", str(src), str(dst)])
        cli.main()
        out = capsys.readouterr().out
        assert not src.exists()
        assert dst.is_file() and dst.read_text() == "z"
        assert "Renamed" in out


def test_bury_deletes_file(tmp_path: Path, monkeypatch, capsys):
    with cwd(tmp_path):
        target = tmp_path / "to_delete.txt"
        target.write_text("bye")
        monkeypatch.setattr(sys, "argv", ["filebunny", "bury", str(target)])
        cli.main()
        out = capsys.readouterr().out
        assert not target.exists()
        assert "Buried" in out

