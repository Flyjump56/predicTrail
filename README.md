# PrédicTrail — par BZHAventure

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
