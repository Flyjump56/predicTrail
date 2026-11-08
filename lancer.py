"""Démarrer le tableau de bord local."""
from pathlib import Path
import sys

# Permet une exécution directe du projet sans installation de paquet.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bzhaventure.server import main


if __name__ == "__main__":
    main()
