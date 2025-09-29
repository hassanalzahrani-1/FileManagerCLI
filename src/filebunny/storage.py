"""
State persistence for filebunny using platformdirs
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json
from platformdirs import user_config_dir

@dataclass
class State:
    """Application state"""
    last_spot: str

class Storage:
    """Handles reading and writing application state"""
    
    def __init__(self):
        config_dir = Path(user_config_dir("filebunny"))
        config_dir.mkdir(parents=True, exist_ok=True)
        self.path = config_dir / "spot.json"

    def read(self) -> State:
        """Read state from disk, return default if not found"""
        if not self.path.exists():
            return State(last_spot=str(Path.cwd()))
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return State(**data)
        except json.JSONDecodeError:
            return State(last_spot=str(Path.cwd()))

    def write(self, state: State) -> None:
        """Write state to disk atomically"""
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        tmp.replace(self.path)