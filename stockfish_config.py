"""Locate Stockfish without starting a process during imports."""
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def stockfish_path() -> str:
    configured = os.environ.get("STOCKFISH_PATH")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        raise FileNotFoundError(f"STOCKFISH_PATH no és un executable vàlid: {candidate}")

    executable = "stockfish.exe" if os.name == "nt" else "stockfish"
    local = ROOT / "engines" / "stockfish" / executable
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    system = shutil.which("stockfish")
    if system:
        return system
    raise FileNotFoundError(
        "No s'ha trobat Stockfish. Executa python scripts/install_stockfish.py "
        "o configura STOCKFISH_PATH."
    )
