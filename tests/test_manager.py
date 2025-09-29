"""
Basic tests for FileManager
"""

import pytest
import tempfile
import os
from pathlib import Path
from filebunny.manager import FileManager
from filebunny.storage import Storage, State

class MockStorage(Storage):
    """Mock storage for testing"""
    def __init__(self, initial_spot: str = None):
        self.state = State(last_spot=initial_spot or str(Path.cwd()))
    
    def read(self) -> State:
        return self.state
    
    def write(self, state: State) -> None:
        self.state = state

def test_spot():
    """Test spot command shows current directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)
        assert os.path.samefile(fm.spot(), tmpdir)

def test_hop():
    """Test hop command changes directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)
        
        # Create a subdirectory
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        
        # Hop to subdirectory
        result = fm.hop("subdir")
        assert os.path.samefile(result, subdir)
        assert os.path.samefile(fm.spot(), subdir)

def test_list():
    """Test list command shows directory contents"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)
        
        # Create some files
        (Path(tmpdir) / "file1.txt").touch()
        (Path(tmpdir) / "file2.txt").touch()
        
        contents = fm.list()
        assert "file1.txt" in contents
        assert "file2.txt" in contents
        assert len(contents) == 2

def test_copy():
    """Test copy command"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)
        
        # Create source file
        src_file = Path(tmpdir) / "source.txt"
        src_file.write_text("test content")
        
        # Copy file
        fm.copy("source.txt", "copy.txt")
        
        # Verify copy exists
        copy_file = Path(tmpdir) / "copy.txt"
        assert copy_file.exists()
        assert copy_file.read_text() == "test content"

def test_move_and_rename_and_delete():
    """Test move, rename, and delete operations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)

        # Create a file
        a = Path(tmpdir) / "a.txt"
        a.write_text("A")

        # Move file
        fm.move("a.txt", "b.txt")
        b = Path(tmpdir) / "b.txt"
        assert b.exists() and not a.exists()

        # Rename file
        fm.rename("b.txt", "c.txt")
        c = Path(tmpdir) / "c.txt"
        assert c.exists() and not b.exists()

        # Delete file
        fm.delete("c.txt")
        assert not c.exists()

def test_dig_and_carrot():
    """Test dig (mkdir -p) and carrot (touch)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)

        # dig creates nested directory
        out_dir = fm.dig("burrow/nest")
        assert Path(out_dir).exists() and Path(out_dir).is_dir()
        assert os.path.samefile(out_dir, Path(tmpdir) / "burrow" / "nest")

        # carrot creates file (and parents if needed)
        out_file = fm.carrot("burrow/nest/carrot.txt")
        p = Path(out_file)
        assert p.exists() and p.is_file()
        assert p.read_text() == ""  # created empty if not exists

def test_hop_errors():
    """Test hop raises on non-existent or non-directory targets"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = MockStorage(tmpdir)
        fm = FileManager(storage)

        # Non-existent path
        with pytest.raises(FileNotFoundError):
            fm.hop("no_such_dir")

        # Create a file and try to hop into it
        f = Path(tmpdir) / "file.txt"
        f.write_text("x")
        with pytest.raises(NotADirectoryError):
            fm.hop("file.txt")

if __name__ == "__main__":
    pytest.main([__file__])
