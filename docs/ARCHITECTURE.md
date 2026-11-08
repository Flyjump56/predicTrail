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
