"""
FileManager class with operations
"""

from pathlib import Path
import shutil
from .storage import Storage, State
from .utils import log_call, log_timing, log_errors

class FileManager:
    """Core file manager with hop/spot operations"""
    
    def __init__(self, storage: Storage):
        self.storage = storage
        self.state = self.storage.read()
        self.cwd = Path(self.state.last_spot)

    def _persist(self):
        """Save current state to disk"""
        self.storage.write(State(last_spot=str(self.cwd)))

    @log_errors
    @log_call
    @log_timing
    def hop(self, path: str | None = None) -> str:
        """Change directory (hop to a new spot)"""
        new = Path(path) if path else Path.home()
        target = (self.cwd / new).resolve() if not new.is_absolute() else new.resolve()
        if not target.exists():
            raise FileNotFoundError(f"path does not exist: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"not a directory: {target}")
        self.cwd = target
        self._persist()
        return str(self.cwd)

    @log_errors
    @log_call
    @log_timing
    def spot(self) -> str:
        """Show current directory (current spot)"""
        return str(self.cwd)

    @log_errors
    @log_call
    @log_timing
    def list(self) -> list[str]:
        """List contents of current directory"""
        return [p.name for p in self.cwd.iterdir()]

    @log_errors
    @log_call
    @log_timing
    def copy(self, src: str, dst: str):
        """Copy file or directory"""
        s, d = self.cwd / src, self.cwd / dst
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    @log_errors
    @log_call
    @log_timing
    def move(self, src: str, dst: str):
        """Move file or directory"""
        shutil.move(str(self.cwd / src), str(self.cwd / dst))

    @log_errors
    @log_call
    @log_timing
    def delete(self, path: str):
        """Delete file or directory"""
        target = (self.cwd / path).resolve()
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=False)

    @log_errors
    @log_call
    @log_timing
    def rename(self, src: str, dst: str):
        """Rename file or directory"""
        (self.cwd / src).rename(self.cwd / dst)

    @log_errors
    @log_call
    @log_timing
    def dig(self, path: str) -> str:
        """Create a directory (mkdir -p behavior) and return its absolute path"""
        target = (self.cwd / path).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    @log_errors
    @log_call
    @log_timing
    def carrot(self, path: str) -> str:
        """Create a file (touch behavior) and return its absolute path"""
        target = (self.cwd / path).resolve()
        # Ensure parent exists; mimic touch by creating parents if needed
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        return str(target)
