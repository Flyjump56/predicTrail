"""Paramètres, chemins du projet et seuils de segmentation morphologique de la version 2.1.0."""
from pathlib import Path
import os
import sys
import shutil

# Les ressources sont repérées depuis le code, indépendamment du dossier courant.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FROZEN = bool(getattr(sys,"frozen",False))
RESOURCE_ROOT = Path(getattr(sys,"_MEIPASS",PROJECT_ROOT))
USER_ROOT = Path(os.environ["PREDICTRAIL_DATA_DIR"]) if os.environ.get("PREDICTRAIL_DATA_DIR") else (
    Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"PredicTrail" if FROZEN else PROJECT_ROOT/"data")
REFERENCES = USER_ROOT / "references"
WEB_DIR = Path(__file__).with_name("web")
PAGE = WEB_DIR / "index.html"
LOGO = RESOURCE_ROOT / "assets" / "logo-bzhaventure.png"
MAX_UPLOAD = 20 * 1024 * 1024
HOST = "127.0.0.1"
PORT = int(os.environ.get("PREDICTRAIL_PORT","8765"))
LOCAL_DATA = USER_ROOT / "local"
DATABASE = LOCAL_DATA / "bzhaventure.sqlite3"

# Classification morphologique indépendante de la distance de la course.
CLASSIFICATION_VERSION = "2.1"
RELIEF_GRID = 25
RELIEF_REVERSAL = 10
PROFILE_LABELS = {
    "flat": "Plat / Vallonné",
    "mountain": "Intermédiaire / Montagne",
    "sawtooth": "Dents de scie",
    "mixed": "Mixte",
}
PROFILE_FAMILIES = {"flat":"flat", "rolling":"flat", "intermediate":"mountain",
                    "mountain":"mountain", "sawtooth":"sawtooth", "mixed":"mixed"}

DISTANCE_CLASSES = [
    ("very_short", "Moins de 20 km", 10),
    ("short", "20 à moins de 50 km", 35),
    ("medium", "50 à moins de 100 km", 75),
    ("long", "100 à moins de 160 km", 130),
    ("ultra", "160 km et plus", 200),
]
DISTANCE_LIMITS = (20, 50, 100, 160)

SOURCE_SAMPLING = {
    "flat": [75, 100, 150, 200, 250],
    "rolling": [40, 50, 75, 100, 125],
    "sawtooth": [25, 25, 40, 50, 60],
    "intermediate": [40, 50, 75, 100, 125],
    "mountain": [50, 75, 100, 150, 200],
    "mixed": [25, 40, 50, 75, 100],
}

# Pas de catalogue : le plus fin de chaque famille. Les parcours conservent
# leur pas initial selon leur morphologie, indépendamment du regroupement.
SAMPLING = {family:[min(SOURCE_SAMPLING[source][i] for source,target in PROFILE_FAMILIES.items() if target==family)
                   for i in range(len(DISTANCE_CLASSES))] for family in PROFILE_LABELS}

INCLINATION_BANDS = [
    ("Descente au-delà de 40 %", -50),
    ("Descente de 25 à 40 %", -32.5),
    ("Descente de 15 à 25 %", -20),
    ("Descente de 8 à 15 %", -11.5),
    ("Descente de 3 à 8 %", -5.5),
    ("Plat · −3 à +3 %", 0),
    ("Montée de 3 à 8 %", 5.5),
    ("Montée de 8 à 15 %", 11.5),
    ("Montée de 15 à 25 %", 20),
    ("Montée de 25 à 40 %", 32.5),
    ("Montée au-delà de 40 %", 50),
]

# Les versions distribuées démarrent avec des exemples fictifs, une seule fois.
if FROZEN:
    REFERENCES.mkdir(parents=True,exist_ok=True)
    marker=USER_ROOT/".demonstration-installee"
    if not marker.exists():
        for example in (RESOURCE_ROOT/"demo").glob("*.gpx"):
            target=REFERENCES/example.name
            if not target.exists():shutil.copy2(example,target)
        marker.write_text("Exemples fictifs PrédicTrail",encoding="utf-8")
