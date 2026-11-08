"""Préparer les seules sources publiables sans reprendre l’historique privé."""
from pathlib import Path
import shutil,sys
from make_demo import make_demo
root=Path(__file__).resolve().parents[1]
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/"build"/"public-source"
if target.exists():raise SystemExit("La préparation existe déjà : choisir un autre dossier.")
target.mkdir(parents=True)
for name in ("src","tests","tools"):
    shutil.copytree(root/name,target/name,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
for name in ("lancer.py","predire.py","Demarrer-BZHAventure.cmd","requirements-garmin.txt","requirements-windows.lock",".gitattributes"):
    shutil.copy2(root/name,target/name)
(target/"assets").mkdir()
for name in ("logo-bzhaventure.png","thème.jpg"):shutil.copy2(root/"assets"/name,target/"assets"/name)
(target/"docs").mkdir()
for name in ("FONCTIONNEL.md","ARCHITECTURE.md","GARMIN.md","MODELE-2.1.md","MODELE-2.0.md","DEMARRAGE-WINDOWS.md","DIFFUSION.md","SAUVEGARDES.md"):
    shutil.copy2(root/"docs"/name,target/"docs"/name)
make_demo(target/"data"/"references")
(target/".gitignore").write_text(".venv/\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\nbackups/\nsorties/\ndata/local/\ndata/parcours/\ndata/references/*\n!data/references/Demonstration-fictive-1.gpx\n!data/references/Demonstration-fictive-2.gpx\n!data/references/Demonstration-fictive-3.gpx\n*.spec\n",encoding="utf-8")
(target/"README.md").write_text("""# PrédicTrail — par BZHAventure

Application locale de prédiction des temps de trail et ultra-trail à partir de GPX de référence.

- Analyse d’un parcours, temps de passage, ravitaillements, stratégie d’allure et de montée.
- Modèles par relief et distance, comparaison de runs avec lecture simultanée.
- Cartes, profils colorés, conversion GPX, sauvegarde et restauration complètes.
- Import Garmin facultatif ; calculs locaux.

## Démarrer depuis les sources

Créer un environnement Python, puis lancer `python -B lancer.py` et ouvrir http://127.0.0.1:8765.
Pour Garmin : `python -m pip install -r requirements-garmin.txt`.
Les GPX inclus sont des démonstrations fictives, sans activité personnelle. Remplacez-les par vos références pour obtenir des estimations personnelles.

## Windows autonome

Consulter [le guide Windows](docs/DEMARRAGE-WINDOWS.md) et [la construction du paquet](docs/DIFFUSION.md).
Le paquet Windows contient Python et les dépendances. Sources testées avec Python 3.15.2.

## Sauvegardes

Utiliser l’écran Sauvegarde et restauration et conserver une copie externe du ZIP. Les données utilisateur ne sont pas publiées dans ce dépôt. Voir [le guide](docs/SAUVEGARDES.md).

## Tests

`python -m unittest discover -s tests` et `node tests/test_web.js`.

## Documentation

[Guide fonctionnel](docs/FONCTIONNEL.md) · [Modèle](docs/MODELE-2.1.md) · [Garmin](docs/GARMIN.md).
Aucune licence open source n’a encore été choisie par l’auteur.
""",encoding="utf-8")
# Une copie de l’historique de travail n’est jamais incluse.
assert not (target/".git").exists()
assert len(list((target/"data").rglob("*.gpx")))==3
print(target)
