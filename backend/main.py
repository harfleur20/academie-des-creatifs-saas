import sys
from pathlib import Path

try:
    from app.main import app
except ModuleNotFoundError as exc:
    if (exc.name or "").split(".")[0] == "app":
        raise
    # Usually a console where the project venv is not active: say so instead of a bare traceback.
    venv = Path(__file__).resolve().parent / ".venv"
    in_venv = Path(sys.prefix).resolve() == venv.resolve()
    hint = (
        "Installez les dépendances : pip install -r requirements.txt"
        if in_venv
        else "Activez le venv du projet depuis backend :\n"
        "  Git Bash   : source .venv/Scripts/activate\n"
        "  PowerShell : .venv\\Scripts\\Activate.ps1\n"
        "puis relancez : uvicorn main:app --reload --port 8000"
    )
    raise SystemExit(
        f"Module Python absent : {exc.name}.\n"
        f"Le backend tourne avec {sys.executable}.\n{hint}"
    ) from exc

__all__ = ["app"]
