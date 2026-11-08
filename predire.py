"""Lancer une prédiction GPX en ligne de commande."""
from pathlib import Path
import sys

# Permet une exécution directe du projet sans installation de paquet.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bzhaventure.cli import main


if __name__ == "__main__":
    main()
