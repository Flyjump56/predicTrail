# Diffusion de PrédicTrail

Le dépôt public https://github.com/Flyjump56/pr-dicTrail contient une copie des sources, illustrations, tests et exemples fictifs. Il ne reprend pas l’historique de développement local contenant des GPX personnels. Les données et sauvegardes restent exclues du dépôt.

## Paquet Windows autonome

Le script tools/build_windows.py construit une distribution Windows x64 avec PyInstaller 6.22.3 et Python 3.15.2, testés sur ce poste. Les dépendances exactes sont listées dans requirements-windows.lock. Créer un environnement de construction dédié, y installer ces dépendances puis lancer python tools/build_windows.py. Le résultat est dans dist/PredicTrail-3.0.0-Windows-x64.zip, accompagné d’une empreinte SHA-256. Décompresser tout le dossier avant de lancer PredicTrail.exe.

Le paquet utilise des données utilisateur séparées dans %LOCALAPPDATA%/PredicTrail. Le binaire contient Python, Garmin et les ressources ; une installation Python externe n’est pas nécessaire. Un compte Garmin reste nécessaire pour l’import Garmin, et sa connexion réelle n’est pas testée par la construction. Le paquet n’est pas signé numériquement. Tester également sur un autre PC Windows avant une diffusion élargie.

## Sauvegarde des sources

Les sources publiques sont préparées par tools/public_snapshot.py dans build/public-source. Cette commande copie uniquement une liste autorisée et génère trois GPX fictifs. Elle refuse d’écraser une préparation existante. Le dépôt Git public doit être initialisé à partir de cette copie propre, sans pousser les branches ou tags de l’historique privé local.

Les sauvegardes de données et les archives Git privées ne doivent pas être ajoutées au dépôt public. Les conditions de licence de l’application restent à définir par l’auteur avant une diffusion plus large.
