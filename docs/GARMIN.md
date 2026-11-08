# Import Garmin Connect

## Installation facultative

Utiliser Python 3.10 ou supérieur (la machine de validation utilise Python 3.9 pour le cœur de l’application). Depuis le dossier du projet :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-garmin.txt
.\.venv\Scripts\python lancer.py
```

Cet exemple nécessite Python 3.12 installé. La dépendance est fixée à `garminconnect==0.2.38`. Le [projet communautaire](https://github.com/cyberjunky/python-garminconnect/tree/0.2.38) et ses [prérequis Python](https://github.com/cyberjunky/python-garminconnect/blob/0.2.38/pyproject.toml) constituent les références de cette intégration. Il s’agit d’un connecteur de compte personnel, dont la compatibilité dépend des services Garmin.

## Utilisation

1. Dans la bibliothèque locale, saisir l’adresse du compte et son mot de passe puis se connecter.
2. Si Garmin le demande, saisir le code MFA. Les secrets et jetons restent uniquement dans la mémoire du serveur ; une nouvelle connexion est nécessaire après son arrêt.
3. Choisir course, vélo, randonnée ou tous les types, les distances minimale et maximale et les dates minimale et maximale. Les bornes sont incluses. Une borne vide n’impose pas cette limite.
4. Lancer l’import. Seules les activités avec une trace GPX chronométrée exploitable sont conservées ; les erreurs sont signalées par activité.
5. Les nouvelles courses à pied peuvent devenir références automatiquement. Le vélo et la randonnée restent stockés sans participer au modèle, sauf sélection explicite dans la liste.

Les distances des filtres sont celles déclarées par Garmin. Le type randonnée inclut la marche et l’alpinisme reconnus par le connecteur. Un nouvel import ignore les activités inchangées et télécharge à nouveau celles dont les métadonnées de révision ont changé. Une modification conserve le choix précédent d’utilisation comme référence. Les contenus GPX identiques ne sont pas dupliqués.

## Suppression et conservation

Les boutons de suppression permettent d’effacer tous les imports locaux ou uniquement ceux correspondant aux critères courants. Une confirmation précise le nombre concerné. Les fichiers du dossier `data/references` et les activités du compte Garmin ne sont pas supprimés. Les modèles sont actualisés après une suppression de références.

La base `data/local/bzhaventure.sqlite3` conserve les imports entre deux démarrages. Elle n’est pas versionnée ; la sauvegarder serveur arrêté. La déconnexion libère la session en mémoire et conserve les activités importées.

## Validation

Les scénarios de connexion, MFA, filtrage, mise à jour et suppression sont testés avec un client simulé. Aucune connexion à un compte Garmin réel n’a été effectuée pendant la validation. Le connecteur optionnel n’est pas installé sur la machine Python 3.9 utilisée pour ces tests.

## Dépannage vérifié avec Python 3.15.2 (version 1.2.3)

Sur cette machine, après le retrait de Python 3.9, le connecteur n’était pas installé dans Python 3.15.2. La commande `python` pointait aussi sur un alias Windows inaccessible et l’ancien lanceur `py` ne détectait pas cette installation. Un environnement `.venv` a été créé dans le projet et `requirements-garmin.txt` y a été installé. Les imports du connecteur, son statut disponible et `pip check` ont été vérifiés avec cet environnement.

Démarrer par double-clic sur **Demarrer-BZHAventure.cmd**, ou depuis le dossier du projet :

```powershell
.\.venv\Scripts\python.exe lancer.py
```

Cette commande utilise le Python et les dépendances du projet. Arrêter auparavant l’ancien serveur avec Ctrl+C, puis recharger le navigateur avec Ctrl+F5. L’état Garmin est affiché en dehors du panneau dépliable. Le panneau de connexion est ouvert par défaut. Les erreurs distinguent désormais dépendance absente, version incompatible, erreur réseau, délai dépassé et réponses HTTP 401, 403 ou 429, sans exposer les secrets.

La validation locale confirme le chargement du connecteur, pas l’authentification d’un compte réel : celle-ci doit être réessayée dans l’interface avec les identifiants du titulaire et, si demandé, son code MFA. Ne pas communiquer ces secrets dans le chat.
