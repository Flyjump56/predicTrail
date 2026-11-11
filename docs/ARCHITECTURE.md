# Architecture, déploiement et démarrage

PrédicTrail 3.0.0 · documentation consolidée le 8 novembre 2026.

[Fonctionnel, sauvegarde et restauration](FONCTIONNEL.md) · [Modèle](MODELE.md)

## Lire ce guide

Les sections principales décrivent la version actuelle. Les documents d’origine sont conservés intégralement en annexes repliables pour la traçabilité ; leurs descriptions datées ne remplacent pas les règles actuelles. Les anciens noms de fichiers restent visibles comme références historiques, mais leurs liens sont redirigés vers ces trois guides.

## Démarrer depuis les sources

Le cœur utilise la bibliothèque standard de Python et accepte Python 3.9 ou supérieur. L’import Garmin facultatif exige Python 3.10 ou supérieur. La version actuellement vérifiée sur ce poste est Python 3.15.2. Depuis la racine du projet, utiliser l’interpréteur de l’environnement du projet :

```powershell
.\.venv\Scripts\python.exe -B lancer.py
```

Pour une nouvelle installation, créer d’abord l’environnement avec un Python compatible installé :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-garmin.txt
.\.venv\Scripts\python.exe -B lancer.py
```

L’installation des dépendances Garmin est facultative pour le calcul local. Le lanceur `Demarrer-BZHAventure.cmd` utilise également l’environnement du projet. Ouvrir [l’application locale](http://127.0.0.1:8765), conserver la console ouverte et arrêter le serveur avec Ctrl+C. Si `python` désigne un alias Windows défectueux ou une autre installation, utiliser le chemin complet du Python souhaité pour créer l’environnement.

L’initialisation affiche ses étapes. Les modes durée, allure et temps enregistrés sont utilisables sans attendre les modèles. Les cartes en ligne et Garmin nécessitent Internet ; les calculs sont locaux et un tracé SVG sert de repli quand Leaflet est indisponible.

<a id="mode-serveur-avec-comptes"></a>

## Mode serveur avec comptes

Le lanceur `lancer_serveur.py` démarre une instance distincte de la version locale. Créer une fois le compte administrateur, puis lancer le serveur depuis le même répertoire de données :

```powershell
.\.venv\Scripts\python.exe lancer_serveur.py --init-admin admin
.\.venv\Scripts\python.exe lancer_serveur.py --port 8766
```

Ouvrir [le serveur de test local](http://127.0.0.1:8766), se connecter et ouvrir **Administration** pour créer les comptes. Le mot de passe initial est défini par l’administrateur. Chaque utilisateur peut le modifier depuis son espace. Les sessions expirent après douze heures et sont révoquées lors d’un changement de mot de passe.

Le répertoire `.predictrail-server/` contient la base des comptes et un sous-dossier privé par utilisateur. Chaque sous-dossier contient les GPX, la base d’activités, les modèles, les scénarios et les sauvegardes du compte. Le navigateur utilise les réglages du serveur et l’ancienne bibliothèque locale reste distincte. `--data-dir` ou `PREDICTRAIL_SERVER_DATA` permet de placer l’ensemble sur un volume persistant. Protéger ce répertoire par les droits du système et l’inclure dans les sauvegardes d’exploitation.

Pour transférer une bibliothèque locale, créer un ZIP complet dans la version locale. Sur le serveur arrêté, indiquer explicitement le compte destinataire et une archive de confiance :

```powershell
.\.venv\Scripts\python.exe lancer_serveur.py --restore-account admin --archive "D:\Sauvegardes\PredicTrail.zip"
```

Utiliser le même `--data-dir` qu’au lancement. Cette opération remplace les données de ce compte, crée une copie avant restauration et laisse la base des comptes séparée. L’utilisateur peut télécharger sa sauvegarde depuis l’application. La restauration ZIP en mode serveur passe par la commande de maintenance.

Pour un accès distant, choisir un nom de domaine et configurer un proxy inverse HTTPS qui conserve l’en-tête `Host` public et transmet vers `127.0.0.1:8766`. Démarrer avec `--port 8766 --origin https://trail.example.org` en remplaçant le domaine d’exemple. Le serveur écoute sur la boucle locale. Les cookies de session utilisent l’attribut Secure avec une origine HTTPS. Vérifier l’accès via le proxy, les limites de transfert, l’espace disque, les sauvegardes et le nombre d’utilisateurs prévu avant l’ouverture. Le mode serveur se teste sur une seule instance de l’application.

### Essai depuis un autre PC du réseau local

Arrêter le serveur local. Relever l’IPv4 privée du PC serveur avec `ipconfig`, puis lancer par exemple `python lancer_serveur.py --port 8766 --lan 192.168.0.203`, en remplaçant l’adresse par celle du PC. Ouvrir cette même adresse et ce même port depuis l’autre PC. Utiliser un compte et un mot de passe de test pendant cet essai HTTP. Le pare-feu Windows doit autoriser le port sur le réseau privé local.

## Démarrer le paquet Windows

Décompresser entièrement le ZIP Windows x64, puis ouvrir `PredicTrail.exe`. Conserver son dossier `_internal` et tous les fichiers livrés. Aucun Python externe n’est nécessaire. Les trois références fournies sont fictives. Le navigateur s’ouvre sur le serveur local ; fermer la console termine l’application.

Les données sont séparées du programme. Avant une mise à jour, créer une sauvegarde complète, remplacer le dossier du programme, puis relancer ; transférer les données d’une installation source vers le paquet par sauvegarde/restauration, pas par copie d’une base ouverte.

## Organisation et responsabilités

| Élément | Responsabilité |
|---|---|
| `lancer.py`, `predire.py`, `cli.py` | Serveur local et commande de rapport/prédiction |
| `settings.py` | Chemins, limites, classes et configuration |
| `gpx.py`, `gpx_import.py` | Lecture, relief, grille adaptative et conversion XML |
| `models.py`, `analysis.py` | Apprentissage, validation, catalogue et analyse des références |
| `prediction.py`, `recorded.py`, `strategy.py` | Intégration des durées, chronologie d’origine et stratégies |
| `storage.py`, `backup.py` | SQLite, caches, état utilisateur, sauvegarde et restauration |
| `garmin.py` | Connexion facultative, filtres, import et annulation |
| `reference_map.py`, `export.py`, `reporting.py` | Géométries, GPX exporté et rapport HTML |
| `server.py`, `validation.py` | API HTTP, travaux asynchrones et processus surveillé |
| `web/index.html`, `styles.css`, `app.js`, `backup.js` | Six écrans, cartes, lecture, impression et sauvegardes |
| `tools/`, `tests/`, `assets/` | Diffusion, vérifications et identité visuelle |

La version applicative se trouve dans `src/bzhaventure/__init__.py`. Les calculs manipulent mètres, secondes et pentes en pourcentage ; les modèles fournissent une allure en secondes par mètre. Les segments GPX restent distincts, sans distance de raccordement artificielle. Les intervalles adaptatifs utilisent leurs bornes réelles, et non un pas supposé uniforme.

## Données et configuration

| Contexte | Emplacement par défaut |
|---|---|
| Exécution depuis les sources | `data/` du projet |
| Paquet Windows | `%LOCALAPPDATA%/PredicTrail` |
| Références natives | `references/` dans ce dossier de données |
| Base SQLite | `local/bzhaventure.sqlite3` |
| Sources des nouveaux parcours conservés | `local/parcours-importes/` |
| Sauvegardes quotidiennes | `local/sauvegardes/` |

`PREDICTRAIL_DATA_DIR` change le dossier des données ; effectuer une sauvegarde avant de le changer. `PREDICTRAIL_PORT` change le port 8765. `PREDICTRAIL_NO_AUTO_BACKUP=1` désactive les sauvegardes quotidiennes automatiques. Ne pas utiliser le même dossier de données avec deux instances simultanées.

SQLite conserve activités importées, choix d’inclusion, analyses, modèles, classification des imports et état utilisateur. Les scénarios, réglages et repères sont synchronisés dans `app_state`. Les données d’anciens navigateurs sont migrées à leur première ouverture. Les secrets et sessions Garmin restent uniquement en mémoire.

Les caches évitent de réanalyser les fichiers inchangés : taille/date, puis empreinte de contenu si nécessaire. Une empreinte du code de calcul et de la version majeure/mineure Python invalide les caches devenus incompatibles. Un fichier modifié en conservant volontairement taille et date peut échapper au premier contrôle. Une signature de contenu et un chargement restreint protègent la désérialisation des caches.

## Serveur, API et surveillance

Le serveur HTTP écoute sur `127.0.0.1` et vérifie l’origine des écritures. Il sert une liste fermée de ressources. Les routes concernent le démarrage, les références et leur sélection, la prédiction, la carte, les conversions, Garmin, l’état utilisateur et les sauvegardes. La prédiction accepte un GPX brut ou une requête JSON avec GPX encodé en base64 ; modes `model`, `total`, `pace`, `recorded`. Les erreurs de saisie donnent HTTP 400 et les modèles indisponibles HTTP 503 ; le suivi et les modes indépendants restent accessibles.

Les écritures et mises à jour sont sérialisées ; références et modèles sont publiés ensemble. La validation s’effectue dans un processus enfant isolé, sans accès à la base utilisateur. Avertissement après 30 secondes sans progression, arrêt après 180 secondes sans progression ou 1 800 secondes au total. Aucun modèle partiel n’est publié. Cette surveillance ne couvre pas la lecture initiale des fichiers ni un appel réseau Garmin en cours.

Limites principales : import analysable de 20 Mio après conversion, source à convertir de 100 Mio ; sauvegarde ZIP de 2 Gio, contenu décompressé de 4 Gio et 10 000 entrées. Les contrôles détaillés de restauration figurent dans le guide fonctionnel.

## Construire et diffuser

Dans un environnement Windows de construction dédié :

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-windows.lock
.\.venv-build\Scripts\python.exe tools/build_windows.py
```

Le script PyInstaller produit `dist/PredicTrail-3.0.0-Windows-x64.zip` et son fichier SHA-256. Le paquet comprend les dépendances, trois démonstrations fictives et les trois guides dans `docs/`, avec une notice `LIRE-MOI.md`. Le mécanisme de processus isolé est activé pour l’exécutable Windows.

Pour préparer les sources publiables :

```powershell
.\.venv\Scripts\python.exe tools/public_snapshot.py build/public-source-nouveau
```

La destination doit être nouvelle. Le script utilise une liste autorisée et génère trois GPX fictifs. Le dépôt public reçoit cette copie propre, sans les GPX personnels, bases, sauvegardes ni l’historique Git privé. Ne pas pousser les branches ou tags de développement privés dans le dépôt public. Git sauvegarde le code ; les ZIP de l’application sauvegardent les données personnelles.

Le paquet n’est pas signé numériquement ; une deuxième machine Windows physique et une authentification Garmin réelle restent à vérifier. La licence de diffusion reste à choisir par l’auteur.

## Vérifier et diagnostiquer

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check src/bzhaventure/web/app.js
node --check src/bzhaventure/web/backup.js
node tests/test_web.js
git diff --check
```

Pour un rapport en ligne de commande : `python predire.py --help` ; `python predire.py --validation` rejoue la validation. Fournir explicitement le chemin GPX évite le sélecteur Tkinter. Vérifier visuellement carte/profil colorés, lecture et plein écran, départ et arrivée, impression, export et sauvegarde/restauration sur un dossier de test.

En cas d’échec, lire la console et le suivi de démarrage, vérifier les GPX rejetés et réduire temporairement la sélection si la validation dépasse les délais. Port occupé : arrêter l’autre instance ou changer `PREDICTRAIL_PORT`. Page ancienne : Ctrl+F5 après redémarrage. Garmin indisponible : vérifier l’interpréteur et les dépendances, puis consulter le guide fonctionnel.

## Contrôle de consolidation

Les 23 documents de `docs/` ont été inventoriés avant modification. Le tableau ci-dessous donne leur destination. Leur contenu complet est repris dans les annexes repliables, avec seulement l’adaptation des liens Markdown. Les anciens résultats sont datés et ne constituent pas une nouvelle mesure de précision.

Une archive locale `backups/documentation-avant-consolidation-20261108.zip` contient les 23 originaux exacts et un manifeste SHA-256. Avant retrait des anciens fichiers, le contrôle vérifie chaque empreinte dans le ZIP et la présence de chaque texte transposé dans sa destination. Cette archive locale est exclue de GitHub ; les annexes et le tableau de correspondance y sont publiés.

| Ancien document | Destination vérifiée |
|---|---|
| `ARCHITECTURE.md` | [ARCHITECTURE.md — annexe source](ARCHITECTURE.md#source-architecture) |
| `DEMARRAGE-WINDOWS.md` | [ARCHITECTURE.md — annexe source](ARCHITECTURE.md#source-demarrage-windows) |
| `DIFFUSION.md` | [ARCHITECTURE.md — annexe source](ARCHITECTURE.md#source-diffusion) |
| `FONCTIONNEL.md` | [FONCTIONNEL.md — annexe source](FONCTIONNEL.md#source-fonctionnel) |
| `GARMIN.md` | [FONCTIONNEL.md — annexe source](FONCTIONNEL.md#source-garmin) |
| `MODELE-2.0.md` | [MODELE.md — annexe source](MODELE.md#source-modele-2-0) |
| `MODELE-2.1.md` | [MODELE.md — annexe source](MODELE.md#source-modele-2-1) |
| `SAUVEGARDES.md` | [FONCTIONNEL.md — annexe source](FONCTIONNEL.md#source-sauvegardes) |
| `VALIDATION-1.1.md` | [MODELE.md — annexe source](MODELE.md#source-validation-1-1) |
| `VALIDATION-1.2.1.md` | [MODELE.md — annexe source](MODELE.md#source-validation-1-2-1) |
| `VALIDATION-1.2.2.md` | [MODELE.md — annexe source](MODELE.md#source-validation-1-2-2) |
| `VALIDATION-1.2.md` | [MODELE.md — annexe source](MODELE.md#source-validation-1-2) |
| `VALIDATION-1.3.md` | [MODELE.md — annexe source](MODELE.md#source-validation-1-3) |
| `VALIDATION-2.0.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-0) |
| `VALIDATION-2.1.2.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-1-2) |
| `VALIDATION-2.1.3.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-1-3) |
| `VALIDATION-2.1.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-1) |
| `VALIDATION-2.2.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-2) |
| `VALIDATION-2.3.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-3) |
| `VALIDATION-2.4.1.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-4-1) |
| `VALIDATION-2.4.md` | [MODELE.md — annexe source](MODELE.md#source-validation-2-4) |
| `VALIDATION-3.0.md` | [MODELE.md — annexe source](MODELE.md#source-validation-3-0) |
| `VALIDATION.md` | [MODELE.md — annexe source](MODELE.md#source-validation) |

## Annexes des documents d’origine

Contenu conservé pour traçabilité. Les indications de version, mesures, limites et emplacements historiques s’interprètent à leur date ; les sections principales ci-dessus font foi pour la version actuelle.

<a id="source-architecture"></a>

<details>
<summary>ARCHITECTURE.md — document source intégral</summary>

# Architecture et maintenance

## Points d'entrée

`lancer.py` démarre le serveur local. `predire.py` lance la commande de prédiction ou de validation. Les lanceurs ajoutent le dossier `src` au chemin d'importation à partir de leur propre emplacement.

La version est déclarée dans `src/bzhaventure/__init__.py`.

## Modules Python

| Module | Responsabilité |
|---|---|
| settings.py | Chemins, adresse locale, limites et tables de segmentation |
| gpx.py | Lecture XML, distances, interpolation, classification et échantillonnage |
| models.py | Courbes d'allure, pondération, régularisation et validation interne |
| prediction.py | Intégration des durées et repères de passage |
| analysis.py | Analyses des références, catalogue, chronologie et estimation des pauses |
| reporting.py | Rapport HTML de la commande |
| cli.py | Arguments et parcours d'exécution en ligne de commande |
| server.py | HTTP, fichiers statiques et démarrage asynchrone |

Les dépendances de calcul sont des modules de la bibliothèque standard de Python. Le client web utilise Leaflet 1.9.4 depuis un CDN et le fond OpenStreetMap.

## Représentation des données

Les distances sont en mètres, les altitudes en mètres, les pentes en pourcentage et les durées en secondes. Les modèles retournent une allure en secondes par mètre.

Un segment est représenté par `(axis, points, samples)`.

- `axis` contient les distances horizontales cumulées des points originaux.
- `points` contient latitude, longitude, altitude et horodatage.
- `samples` contient les points d'analyse et, dans les grilles adaptatives, leur distance locale en cinquième valeur.

`Course` conserve la classification et les caches d'échantillonnage et de portions. Les calculs consomment les données après leur construction. Pour prendre en compte des données modifiées, relire le GPX et créer une nouvelle course.

`sample_intervals` constitue le point d'accès commun aux intervalles d'analyse. Les consommateurs utilisent les bornes réelles. Ils ne supposent pas que le pas soit uniforme.

Les ruptures entre segments GPX sont conservées. Les distances de raccordement ne sont pas ajoutées.

## Modèles

`PaceModel` interpole une courbe d'allure bornée selon la pente. `InclinationModel` évalue une classe discrète et conserve donc son comportement spécifique lors d'une copie de sélection.

`SegmentedModel` prépare une courbe globale et une courbe historique. Il construit les candidats par profil et distance, puis valide le profil sur les références disponibles. Les sous-modèles sont mis en cache pendant les validations imbriquées.

La validation externe retire chaque course avant apprentissage. La validation interne qui choisit le modèle utilise seulement les courses restantes. Les métadonnées de choix appartiennent à la requête et sont copiées avant modification.

Les pauses sont estimées comme une part de la durée totale déjà apprise. Toute évolution vers une planification d'arrêts devra préserver cette règle pour éviter un double comptage.

## Serveur et démarrage

Le serveur écoute par défaut sur `127.0.0.1:8765`. L'initialisation se fait dans un fil de travail pendant que le serveur répond à la page et au suivi.

`StartupStatus` protège les informations partagées par un verrou. Les modèles et les références sont publiés avant le passage à l'état prêt. Les requêtes de données reçoivent HTTP 503 pendant le chargement ou après un échec.

Les fichiers statiques sont distribués à partir d'une liste fermée de routes.

| Route | Méthode | Rôle |
|---|---|---|
| / | GET | Page du tableau de bord |
| /api/startup | GET | Phase, progression, compteurs et durée |
| /api/references | GET | Références, modèles et validations |
| /api/prediction | POST | Analyse d'un GPX envoyé dans le corps |
| /assets/styles.css | GET | Présentation et impression |
| /assets/app.js | GET | Contrôleur de l'interface |
| /assets/logo-bzhaventure.png | GET | Logo fourni |

Le POST attend `Content-Type: application/gpx+xml`. Les paramètres sont `pas-km` et `model`.

Les choix de modèle sont `auto`, `global`, `inclination` ou `profil:distance`. Les clés de profil sont `flat`, `rolling`, `sawtooth` et `mountain`. Les clés de distance sont `short`, `medium`, `long` et `ultra`.

Une entrée invalide reçoit HTTP 400. Une ressource absente reçoit HTTP 404. Les erreurs métier de prédiction et les états d'initialisation sont transmis en JSON.

## Interface web

`index.html` définit les écrans. `styles.css` regroupe présentation, plein écran et impression. `app.js` orchestre les appels et le rendu.

Le contrôleur partage une chronologie entre carte, profil, curseur et horaires. La coloration réutilise la même valeur et les mêmes bornes dans la carte et le profil.

Les tracés Leaflet utilisent le même moteur SVG pour respecter l'ordre du contour, des portions colorées et des marqueurs. Les commandes de lecture sont des descendants du panneau de carte pour rester accessibles en plein écran.

Les horaires sont calculés dans le navigateur. La saisie locale est convertie en instant, puis les secondes sont ajoutées à cet instant. Le contrôle détecte une heure locale inexistante lors du passage à l'heure d'été.

Le suivi du démarrage interroge le serveur toutes les secondes. Il s'arrête lorsque les références sont chargées ou qu'une erreur de démarrage est affichée.

## Ajouter des références

1. Copier les nouveaux GPX chronométrés dans `data/references`.
2. Redémarrer le serveur.
3. Consulter les fichiers écartés et la couverture des groupes.
4. Comparer les erreurs médianes et moyennes.
5. Examiner les écarts par course et les interruptions d'enregistrement.

Les seuils et pas de groupe figurent dans `settings.py` et les règles de calcul dans `gpx.py` et `models.py`. Toute modification doit être accompagnée d'une nouvelle validation sur les références.

## Vérifier une modification

Depuis la racine du projet, exécuter les commandes suivantes.

~~~powershell
python -B -m unittest discover -s tests -v
node --check src/bzhaventure/web/app.js
~~~

Les tests ciblent la lecture GPX, les pas non uniformes, les unités, les modèles, les pauses, les ressources web et l'état de démarrage.

Pour rejouer la validation complète, démarrer l'application. La progression et les résultats sont disponibles dans le tableau de bord. La commande `python predire.py --validation` fournit également la validation des temps d'arrivée.

Pour une vérification visuelle, importer un parcours, modifier le modèle et les repères, saisir un départ, lire la trace, tester le zoom et le plein écran, puis ouvrir l'impression. Vérifier ensemble carte, profil, dates et totaux.

## Versionner une évolution

~~~powershell
git status
git diff
git add chemin-du-fichier
git commit -m "Description de la modification"
~~~

Le jalon initial est `v1.0.0`. Les traces et archives fournies sont incluses dans ce jalon. Les environnements virtuels, caches et sorties calculées usuelles sont ignorés.

## Diagnostic

- Si le port est occupé, arrêter l'instance déjà ouverte avant de relancer.
- Si la page montre un échec de démarrage, lire le message dans la page ou le terminal et vérifier les références.
- Si les modifications web sont invisibles, actualiser avec Ctrl+F5.
- Si le fond de carte manque, vérifier la connexion à Leaflet et OpenStreetMap.
- Si le navigateur intégré bloque l'aperçu d'impression, ouvrir l'application dans un navigateur de bureau.
- Si les dates semblent décalées, vérifier le fuseau horaire de l'appareil.

## Stockage et import — version 1.1

`storage.py` gère la base SQLite locale, les empreintes, filtres et transactions. `garmin.py` encapsule le connecteur optionnel, le MFA, la sélection et le téléchargement des activités. Les tables `activities`, `reference_cache` et `model_cache` séparent les GPX importés des résultats dérivés. Les imports conservent leur révision distante et leur choix d’utilisation comme référence.

Le cache des modèles dépend des empreintes des références et du code de calcul, ainsi que de la version majeure/mineure de Python. Les objets sont protégés par une somme SHA-256 et désérialisés avec une liste explicite de classes autorisées. Les anciens modèles sont élagués après enregistrement du nouveau. Les caches temporaires de validation imbriquée ne sont pas sérialisés.

Le serveur sérialise les opérations de modification par verrou et publie une paire `(modèles, références)` cohérente. La suppression de références importées invalide immédiatement le cache des modèles. Les imports partiellement réussis sont conservés et entraînent également une actualisation. Les identifiants Garmin et la session ne sont pas écrits sur disque. Les requêtes sont limitées à l’hôte local avec contrôle d’origine sur les POST.

### API ajoutées

| Route | Usage |
|---|---|
| GET /api/local | Bibliothèque et état du connecteur |
| GET /api/operation | Progression de l’opération courante |
| GET /api/garmin/status | Disponibilité et connexion |
| POST /api/references/refresh | Actualiser les références et modèles |
| POST /api/local/upload | Ajouter un GPX encodé en base64 |
| POST /api/local/reference | Modifier le booléen `reference` d’un `id` |
| POST /api/local/delete | Supprimer `scope: all` ou `matching` avec `filters` |
| POST /api/garmin/connect | Connexion avec `email` et `password` |
| POST /api/garmin/mfa | Transmettre `code` |
| POST /api/garmin/disconnect | Libérer la session |
| POST /api/garmin/import | Importer selon `filters` et `useRunning` |

Les filtres partagent `kind` (all/running/cycling/hiking), `minKm`, `maxKm`, `minDate`, `maxDate`. Les bornes sont inclusives et validées.

`POST /api/prediction` accepte toujours le GPX brut historique, ainsi qu’un objet JSON avec `gpx` en base64, `mode` (model/total/pace), `model`, `interval`, `totalSeconds`, `paceSeconds` et `waypoints: [{km, comment}]`. Les modes manuels construisent un modèle constant sans attendre les références. Les repères personnalisés utilisent l’interpolation et la même intégration temporelle que les repères réguliers.

Le contrôleur web numérote les analyses pour ignorer les réponses réseau obsolètes. `tests/test_v11.py` couvre stockage, prédiction, API et Garmin simulé ; `tests/test_web.js` vérifie les interactions avec un DOM et un réseau simulés, sans dépendance npm.

## Version 1.2 : sélection, export et scénarios

La table SQLite `reference_selection(key, enabled)` conserve l’exclusion des fichiers natifs. Les imports utilisent leur colonne `reference` existante. `Store.reference_inventory` réunit tous les fichiers sélectionnables ; `reference_sources` ne fournit que les sources actives aux calculs et à leur empreinte de cache. La sélection efface le cache du modèle, puis déclenche le mécanisme transactionnel d’actualisation existant. Le choix est validé contre l’inventaire pour refuser les clés arbitraires.

`GET /api/reference-selection` renvoie `references: [{key, name, enabled}]`. `POST /api/reference-selection` reçoit `{key, enabled: bool}` et démarre un recalcul asynchrone. L’API d’import GPX 1.1 est réutilisée.

`export.py` intègre les allures des intervalles d’analyse aux distances des points originaux en temps linéaire, en conservant les segments. La réponse `/api/prediction` ajoute `exportPoints`, une liste de segments de points `[latitude, longitude, altitude, secondesDepuisDépart]`. Le client génère le XML GPX, échappe les textes, ajoute les repères et convertit les dates en UTC avant téléchargement par Blob.

La navigation conserve le DOM de la carte et invalide sa taille au retour à l’analyse. Le classement et l’erreur de validation exploitent les données déjà calculées. Les scénarios sont des instantanés JSON stockés sous `bzhaventure-runs-v1` dans localStorage. Une empreinte compacte du fichier distingue les parcours pour les comparaisons ; ce mécanisme d’interface n’est pas un contrôle de sécurité. Les fichiers GPX encodés ne sont pas dupliqués dans ce stockage. Les exceptions de quota sont visibles pour l’utilisateur.

## Version 1.2.1

`GET /api/runtime` renvoie les versions Python (`platform.python_version`) et application. La validation des références ajoute `groupEstimated` et `groupReferenceCount` : une courbe est apprise avec `learn_curve` sur les autres références partageant profil et classe de distance, sans repli global. Ce changement de code invalide automatiquement les caches de calcul. Les estimations automatiques historiques restent disponibles pour les autres indicateurs du modèle.

`rankReferenceGroups` trie les courses en groupes, calcule les rangs de performance et les proximités de façon indépendante. L’écran Simulation utilise directement `/api/prediction` avec ses propres fichiers et paramètres, puis stocke des instantanés dans la comparaison existante, sans modifier l’analyse active.

## Version 1.2.2 : chronologie enregistrée

`recorded.py` construit une réponse de comparaison à partir des points horodatés. Le mode JSON `recorded` de `/api/prediction` est traité avant toute sélection ou intégration de modèle et fonctionne pendant l’initialisation. Il ajoute `recordedStart` (ISO UTC) et un modèle descriptif de portée `recorded`, sans courbe apprise. Les coordonnées et temps relatifs sont disponibles dans `exportPoints`. Le contrôleur de simulation utilise `recordedStart` plutôt que le champ de départ manuel.

Les tests vérifient les interruptions de segments, l’interpolation des repères, le refus des dates absentes et l’absence d’appels à `predict` ou `manual_model`. Les données réelles ne sont pas injectées dans l’état de l’analyse prédictive.

## Version 1.3 : processus surveillé et géométries des références

`validation.py` regroupe la construction de l’instantané et son exécution isolée via `multiprocessing` en mode spawn. Un pipe transporte les événements de progression et le résultat final. Le superviseur mesure le temps depuis la dernière progression et la durée totale ; il termine puis joint le processus en dépassement ou en erreur. Le processus enfant n’écrit pas dans SQLite. Seul le parent publie l’instantané complet et son cache. Le serveur créé par `main` active cette isolation ; les usages directs sans ce drapeau conservent la construction en ligne pour les tests et l’API Python historique.

`StartupStatus` expose `lastProgressAgo`, `slow`, `validationTimeout`, `cancelRequested`. Les seuils de production sont `STALL_SECONDS=180` et `TOTAL_SECONDS=1800`.

`POST /api/garmin/stop` positionne l’Event de l’opération Garmin, sans acquérir le verrou de session occupé par l’import. La lecture des activités utilise l’API du connecteur par pages de 20 pour pouvoir vérifier cet Event entre requêtes. L’Event est vérifié avant chaque téléchargement et avant l’enregistrement du fichier reçu. Le bilan comprend `cancelled`. L’actualisation des modèles suit toujours un import partiel.

`GET /api/reference-map` utilise `reference_map.py` pour lire les sources natives et importées, actives et exclues. Le cache d’analyse existant est réutilisé. La géométrie fournie est allégée à environ 1 500 points par course, avec les extrémités de chaque segment préservées. Les données d’analyse et les fichiers originaux restent intacts. Le client gère une seconde instance Leaflet et un secours SVG indépendant de la carte de prédiction. L’histogramme SVG compte les lignes d’analyse par profil et classe de distance.

## Modèle 2.0

`settings.py` définit six profils, cinq classes, les pas cibles et `CLASSIFICATION_VERSION`. `describe_course` retourne une version de description, sa règle d’attribution, `ascentDensity`, `steepDistanceShare`, `climbShares`, `climbCounts`, fréquences et médianes des ascensions. Les anciens objets de classification ne sont pas réutilisés si la version diffère. Les clés `reliefDensity`, `longReliefShare` et `medianReliefLength` restent présentes pour compatibilité ; la part longue correspond désormais au D+ des grandes ascensions.

`relief_similarity` pondère les références d’un profil selon cinq dimensions morphologiques continues. Le descripteur réel est transmis par `for_course` et par la sélection manuelle. Pour une courbe de catalogue sans parcours cible, une référence représentative proche de la distance centrale du groupe sert de morphologie cible ; les métadonnées décrivent ce choix. La validation interne utilise les nouvelles pondérations et conserve le repli conservateur. Le nombre de groupes de catalogue et sa progression sont calculés depuis les tables de paramètres, sans constante de 16 groupes.

Les sorties HTTP conservent leur structure et ajoutent les indicateurs dans `classification`. Les métadonnées des candidats comprennent `morphologyWeighted`, `morphologySimilarities`, les densités, fréquences et médianes cibles. Les changements de `gpx.py`, `settings.py` et `models.py` invalident les empreintes SQLite existantes ; aucune migration destructive des activités n’est nécessaire.

## Version 2.1

`PROFILE_FAMILIES` rattache les six morphologies à quatre clés : flat, mountain, sawtooth et mixed. `PROFILE_LABELS` ne contient que ces familles d’apprentissage. `SOURCE_SAMPLING` conserve les anciens pas par morphologie, et `SAMPLING` décrit les minima du catalogue des familles. Les classifications de version 2.1 ajoutent `sourceProfile`. `select_candidate` conserve le pas du descripteur cible lorsque sa famille correspond au modèle choisi. Les alias de sélection rolling et intermediate sont normalisés.

Le contrôleur conserve les références et objets de lignes construits dans le DOM. La sélection d’une barre applique un filtre visuel sans modifier les données ou la sélection d’apprentissage. Les états d’expansion sont conservés séparément de la visibilité. Les barres SVG sont des boutons accessibles au clavier ; la liste du groupe utilise textContent et des callbacks explicites vers les branches. Les classes CSS references-wide et reference-ranking maîtrisent la largeur, les retours à la ligne et la présentation mobile.

</details>

<a id="source-demarrage-windows"></a>

<details>
<summary>DEMARRAGE-WINDOWS.md — document source intégral</summary>

# PrédicTrail — par BZHAventure

Décompressez entièrement l’archive ZIP dans un dossier de votre choix, puis ouvrez PredicTrail.exe. Python et les dépendances Garmin sont inclus. Conservez la fenêtre de lancement ouverte pendant l’utilisation ; le navigateur s’ouvre à http://127.0.0.1:8765. Fermer la fenêtre de lancement arrête le serveur local.

Les exemples fournis sont fictifs et servent uniquement à découvrir l’interface. Importez vos propres courses chronométrées pour construire un modèle personnel. Les cartes en ligne et Garmin nécessitent Internet ; les calculs restent locaux et une trace sans fond de carte reste disponible.

Les données personnelles sont enregistrées séparément de l’application dans %LOCALAPPDATA%/PredicTrail. Changer de version en remplaçant le dossier du programme ne remplace pas ce dossier de données. En mode sources, le dossier data du projet reste utilisé. L’emplacement peut être changé avec PREDICTRAIL_DATA_DIR ; ne changez pas ce réglage sans sauvegarde.

## Sauvegarde

Ouvrez Sauvegarde et restauration puis Créer une sauvegarde complète. Téléchargez le ZIP et copiez-le sur un autre support. La sauvegarde inclut les références GPX, parcours conservés, imports, sélections, modèles, scénarios, réglages et repères. Les identifiants et sessions Garmin ne sont pas sauvegardés.

Une copie locale automatique est créée une fois par jour au premier démarrage réussi. Toutes les copies sont conservées dans le sous-dossier local/sauvegardes ; aucune suppression automatique. Une copie sur le même disque ne protège pas d’une panne du disque.

Pour restaurer, sélectionnez le ZIP, vérifiez la date et la version puis cliquez Restaurer les données. Le contenu est vérifié avant remplacement et une copie de sécurité est créée. Les modèles peuvent être recalculés. Reprendre le dernier parcours réouvre son GPX conservé ; les scénarios sont disponibles dans Simulation. Les anciens scénarios du navigateur sont repris à la première ouverture dans ce navigateur.

## Distribution

Ce paquet contient uniquement le programme, les illustrations de l’application et des exemples fictifs. Aucune course personnelle ni connexion Garmin n’y est incluse. Le programme n’est pas signé numériquement. Les conditions de licence et de diffusion publique restent à définir par l’auteur.

</details>

<a id="source-diffusion"></a>

<details>
<summary>DIFFUSION.md — document source intégral</summary>

# Diffusion de PrédicTrail

Le dépôt public https://github.com/Flyjump56/pr-dicTrail contient une copie des sources, illustrations, tests et exemples fictifs. Il ne reprend pas l’historique de développement local contenant des GPX personnels. Les données et sauvegardes restent exclues du dépôt.

## Paquet Windows autonome

Le script tools/build_windows.py construit une distribution Windows x64 avec PyInstaller 6.22.3 et Python 3.15.2, testés sur ce poste. Les dépendances exactes sont listées dans requirements-windows.lock. Créer un environnement de construction dédié, y installer ces dépendances puis lancer python tools/build_windows.py. Le résultat est dans dist/PredicTrail-3.0.0-Windows-x64.zip, accompagné d’une empreinte SHA-256. Décompresser tout le dossier avant de lancer PredicTrail.exe.

Le paquet utilise des données utilisateur séparées dans %LOCALAPPDATA%/PredicTrail. Le binaire contient Python, Garmin et les ressources ; une installation Python externe n’est pas nécessaire. Un compte Garmin reste nécessaire pour l’import Garmin, et sa connexion réelle n’est pas testée par la construction. Le paquet n’est pas signé numériquement. Tester également sur un autre PC Windows avant une diffusion élargie.

## Sauvegarde des sources

Les sources publiques sont préparées par tools/public_snapshot.py dans build/public-source. Cette commande copie uniquement une liste autorisée et génère trois GPX fictifs. Elle refuse d’écraser une préparation existante. Le dépôt Git public doit être initialisé à partir de cette copie propre, sans pousser les branches ou tags de l’historique privé local.

Les sauvegardes de données et les archives Git privées ne doivent pas être ajoutées au dépôt public. Les conditions de licence de l’application restent à définir par l’auteur avant une diffusion plus large.

</details>
