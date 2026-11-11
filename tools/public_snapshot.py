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
for name in ("lancer.py","lancer_serveur.py","predire.py","Demarrer-BZHAventure.cmd","requirements-garmin.txt","requirements-windows.lock",".gitattributes"):
    shutil.copy2(root/name,target/name)
(target/"assets").mkdir()
for name in ("logo-bzhaventure.png","thème.jpg"):shutil.copy2(root/"assets"/name,target/"assets"/name)
(target/"docs").mkdir()
for name in ("ARCHITECTURE.md","FONCTIONNEL.md","MODELE.md"):
    shutil.copy2(root/"docs"/name,target/"docs"/name)
make_demo(target/"data"/"references")
(target/".gitignore").write_text(".venv/\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\nbackups/\nsorties/\n/.predictrail-server/\ndata/local/\ndata/parcours/\ndata/references/*\n!data/references/Demonstration-fictive-1.gpx\n!data/references/Demonstration-fictive-2.gpx\n!data/references/Demonstration-fictive-3.gpx\n*.spec\n",encoding="utf-8")
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

Consulter [Architecture, déploiement et démarrage](docs/ARCHITECTURE.md).
Le paquet Windows contient Python et les dépendances. Sources testées avec Python 3.15.2.

## Mode serveur avec comptes

Initialiser l’administrateur avec `python lancer_serveur.py --init-admin admin`, puis lancer `python lancer_serveur.py --port 8766`.
Voir le [guide du mode serveur](docs/ARCHITECTURE.md#mode-serveur-avec-comptes) pour créer les utilisateurs et préparer l’accès HTTPS.

## Sauvegardes

Utiliser l’écran Sauvegarde et restauration et conserver une copie externe du ZIP. Les données utilisateur ne sont pas publiées dans ce dépôt. Voir [Fonctionnel, sauvegarde et restauration](docs/FONCTIONNEL.md).

## Tests

`python -m unittest discover -s tests` et `node tests/test_web.js`.

## Documentation

[Architecture, déploiement et démarrage](docs/ARCHITECTURE.md) · [Fonctionnel, sauvegarde et restauration](docs/FONCTIONNEL.md) · [Modèle](docs/MODELE.md).
Les trois guides incluent la correspondance des 23 anciens documents et leurs annexes historiques intégrales.
Aucune licence open source n’a encore été choisie par l’auteur.
""",encoding="utf-8")
# Une copie de l’historique de travail n’est jamais incluse.
assert not (target/".git").exists()
assert len(list((target/"data").rglob("*.gpx")))==3
print(target)
