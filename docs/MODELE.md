# Modèle prédictif

PrédicTrail 3.0.0 · classification 2.1 · documentation consolidée le 8 novembre 2026.

[Architecture, déploiement et démarrage](ARCHITECTURE.md) · [Fonctionnel, sauvegarde et restauration](FONCTIONNEL.md)

## Règles actuelles et historique

Les règles courantes sont présentées ci-dessous. Les deux anciennes spécifications et les quinze comptes rendus de validation sont conservés intégralement dans les annexes repliables. Ils décrivent leurs versions et leurs jeux de données d’alors. En particulier, les 30 groupes de la version 2.0 ont été remplacés par 20 groupes, « Dent de scie » se lit désormais « Dents de scie », les stratégies ont été déplacées dans Analyse en 2.4.1 et les scénarios sont centralisés en SQLite depuis 3.0. La restriction GitHub 403 mentionnée dans le compte rendu 3.0 a ensuite été levée et les sources ont été publiées.

## Entrées et préparation

Une référence exploitable fournit latitude, longitude, altitude et horodatages cohérents, avec durée positive. Une trace à prédire peut ne pas avoir de dates. Les distances horizontales sont calculées à partir des coordonnées ; les ruptures de segments restent séparées. Les données source ne sont pas modifiées.

Pour classifier le relief, rééchantillonner tous les 25 m, appliquer un filtre médian sur trois points et ignorer les inversions inférieures à 10 m. Les pentes de classification utilisent une fenêtre de 100 m. Le D+ lissé de classification peut donc différer du D+ récapitulatif de la trace d’analyse. Les pentes utilisées pour apprendre les allures restent celles de l’analyse, pas celles de cette seule fenêtre.

## Reconnaissance de la morphologie

| Ascension | Gain et longueur |
|---|---|
| Petite | Gain inférieur à 100 m |
| Grande | Gain au moins 500 m, ou au moins 300 m sur au moins 5 km |
| Intermédiaire | Autres ascensions significatives |

Le classement suit cet ordre de priorité :

1. Montagne : au moins 50 % du D+ dans les grandes ascensions.
2. Plat : D+ inférieur à 5 m/km et moins de 10 % de distance en pentes dépassant ±3 %.
3. Petites bosses répétées : au moins 60 % du D+ dans les petites ascensions, au moins quatre par 10 km, D+ au moins 10 m/km et longueur médiane des petites ascensions au plus 1 km.
4. Faiblement vallonné : D+ inférieur à 20 m/km après les exclusions précédentes.
5. Intermédiaire soutenu : au moins 50 % du D+ dans les ascensions intermédiaires.
6. Mixte : autres compositions.

Ces règles sont propres à l’application. Elles ne reconnaissent ni un nom de course ni une altitude absolue. Une seule grande ascension peut déterminer un profil montagne si elle représente la majorité du D+ ; la composition détaillée aide à interpréter ce résultat.

## Familles, distance et grille d’analyse

| Famille actuelle | Morphologies conservées |
|---|---|
| Plat / Vallonné | Plat et faiblement vallonné |
| Intermédiaire / Montagne | Intermédiaire soutenu et montagne |
| Dents de scie | Petites bosses répétées |
| Mixte | Relief mixte |

Cinq classes : moins de 20 km ; 20 à moins de 50 ; 50 à moins de 100 ; 100 à moins de 160 ; 160 km et plus. Les bornes inférieures sont incluses. Quatre familles × cinq distances donnent **20 groupes**, y compris les groupes vides affichant leur repli.

La morphologie d’origine, `sourceProfile`, conserve son pas cible malgré les fusions :

| Morphologie / pas en mètres | <20 km | [20,50[ | [50,100[ | [100,160[ | ≥160 |
|---|---:|---:|---:|---:|---:|
| Plat | 75 | 100 | 150 | 200 | 250 |
| Vallonné | 40 | 50 | 75 | 100 | 125 |
| Dents de scie | 25 | 25 | 40 | 50 | 60 |
| Intermédiaire | 40 | 50 | 75 | 100 | 125 |
| Montagne | 50 | 75 | 100 | 150 | 200 |
| Mixte | 25 | 40 | 50 | 75 | 100 |

Les sommets et creux significatifs complètent la grille ; le pas réel peut varier. Le catalogue indique le pas minimal de la famille. Choisir la famille du parcours conserve son pas d’origine ; choisir une autre famille applique le pas de celle-ci. Les anciens identifiants `rolling` et `intermediate` restent des alias. L’espacement des repères utilisateur (1 à 50 km) est indépendant de cette grille d’analyse.

## Apprentissage et sélection

Le modèle relie pente et allure, puis intègre les temps sur les portions du parcours. Il prépare une courbe globale, des candidats par famille/distance et une référence historique à pas de 100 m. Cette dernière n’est pas le résultat de la dernière version précédente.

Les candidats pondèrent les références selon proximité de distance, classe de distance et similarité de morphologie : densité de D+, fréquence, composition, longueur et gain des ascensions. La similarité vaut 1 pour des descriptions identiques et descend jusqu’à 0,05. Le faible support renforce la régularisation vers la courbe globale ; le recalage de durée selon la distance utilise les mêmes poids.

Le mode automatique sélectionne le candidat seulement si la validation interne montre un avantage suffisant ; sinon, il garde son repli global. La sélection manuelle d’un groupe applique son candidat régularisé. La variante expérimentale distingue onze classes d’inclinaison : plat entre −3 et +3 %, puis montée et descente selon 3/8/15/25/40 %. Le manque d’observations entraîne un repli explicite. Le graphique de pente et son tableau dépendent du modèle affiché.

## Pauses et stratégies

Une pause observée correspond à une séquence d’au moins 60 secondes à une vitesse au plus 0,5 km/h. Les intervalles de plus de 300 secondes et coupures de segments sont distingués comme interruptions d’enregistrement. Les références permettent d’estimer une part de pauses dans la durée totale déjà apprise : elle est décomposée, pas ajoutée au total. Il ne s’agit pas de planifier des arrêts à chaque ravitaillement.

Les modes durée et allure utilisent le temps fourni par l’utilisateur, sans ajout automatique de pauses apprises. Le mode enregistré reprend les dates source et ne passe pas par un modèle. Les stratégies de split, montée et ajustement global sont appliquées après l’estimation ; elles ne réentraînent pas le modèle. Leur formule et un exemple figurent dans le guide fonctionnel.

## Validation et classement

La validation externe retire chaque course de l’apprentissage avant de la prédire. Le choix automatique est lui-même validé uniquement sur les références restantes, pour éviter d’utiliser la course testée dans le choix du modèle. La validation interne demande un support suffisant et compare l’amélioration à son incertitude.

Le classement par proximité utilise seulement les autres courses de même famille et classe de distance. Une course seule n’a pas de score de proximité de groupe ; les erreurs du mode automatique et les erreurs de classement de groupe restent distinctes. Le classement de performance par kilomètre-effort n’est pas une mesure d’erreur prédictive.

Présenter médiane et moyenne des erreurs absolues, effectifs et écarts individuels. Les erreurs par pente peuvent se compenser dans une durée totale ; une seule mesure globale ne suffit pas. L’histogramme montre la couverture des 20 groupes et son filtre ne modifie pas l’apprentissage. Les modèles sont recalculés après modification des références ou invalidation des caches ; les anciens scénarios restent figés.

## Résultats conservés et limites

Les essais historiques sur 16 références donnent pour le jalon initial une erreur absolue médiane de 6,3193 % et moyenne de 9,7226 %. La version 2.0 obtient 6,8231 % et 9,7907 % : la nouvelle segmentation n’a donc pas démontré une amélioration sur cet échantillon. La fusion 2.1 applique le choix de regroupement sans garantie de gain de précision. Ces chiffres ne sont pas une mesure recalculée de la version actuelle ni une garantie pour une autre personne.

Le compte rendu 3.0 consigne 74 tests Python, des contrôles Node, la construction Windows et un essai de sauvegarde/restauration sur données fictives. L’authentification Garmin réelle, une seconde machine Windows physique et la signature du binaire restent hors de cette validation. Les rapports complets ci-dessous précisent les résultats, environnements, tests visuels et limites de chaque jalon.

La météo, la technicité, le sol et l’altitude physiologique ne sont pas explicitement représentés. Toute optimisation demande une validation sur des courses nouvelles, au-delà du jeu servant à ajuster les seuils.

## Annexes des documents d’origine

Contenu conservé pour traçabilité. Les indications de version, mesures, limites et emplacements historiques s’interprètent à leur date ; les sections principales ci-dessus font foi pour la version actuelle.

<a id="source-modele-2-0"></a>

<details>
<summary>MODELE-2.0.md — document source intégral</summary>

# Modèle prédictif 2.0 : distance et morphologie du relief

Cette version conserve les fonctions de la version 1.3 et remplace sa classification du relief. Les seuils sont propres à l’application ; ils ne constituent pas une classification officielle des courses.

## Préparation du profil

La classification repose sur les coordonnées et altitudes originales, rééchantillonnées tous les 25 m. Un filtre médian sur trois points retire les pics isolés sans modifier le fichier source. Les inversions de moins de 10 m sont ignorées pour identifier les ascensions ; les replats et petits creux restent dans la même phase. Les segments GPX ne sont jamais raccordés artificiellement. Les variations inférieures à 10 m ne contribuent pas au D+ de classification.

Les pentes de classification sont mesurées sur une fenêtre de 100 m. Le D+ de classification est donc une mesure lissée, qui peut différer du D+ du récapitulatif historique calculé sur la trace d’analyse. Le D+ lissé est explicitement identifié dans les détails. Les pentes utilisées par l’apprentissage et les temps enregistrés ne sont pas remplacés par les pentes de cette fenêtre de classification.

## Types d’ascension

| Type | Règle |
|---|---|
| Petite | Gain vertical inférieur à 100 m |
| Grande | Gain au moins égal à 500 m, ou gain au moins égal à 300 m sur au moins 5 km |
| Intermédiaire | Autres ascensions significatives |

Pour chaque type : nombre d’ascensions et part du D+ total. La longueur et le gain médians, la fréquence par 10 km et la densité de D+ sont également conservés. L’altitude absolue ne détermine pas le type d’ascension.

La limite d’environ 1 km des petites bosses est appliquée à leur longueur médiane pour reconnaître le profil côtier, et non à chaque ascension individuellement. Ce réglage évite qu’une montée côtière de faible amplitude, légèrement plus longue ou fusionnée avec un replat, change artificiellement de nature.

## Attribution du profil, par ordre de priorité

1. **Montagne** : au moins 50 % du D+ dans les grandes ascensions.
2. **Plat ou presque plat** : D+ inférieur à 5 m/km et moins de 10 % de distance en pente supérieure à +3 % ou inférieure à −3 %.
3. **Petites bosses répétées / côtier** : au moins 60 % du D+ dans les petites ascensions, au moins quatre petites ascensions par 10 km, D+ au moins égal à 10 m/km et longueur médiane des petites ascensions au plus égale à 1 km.
4. **Faiblement vallonné** : D+ inférieur à 20 m/km, après exclusion des profils précédents.
5. **Relief intermédiaire soutenu** : au moins 50 % du D+ dans les ascensions intermédiaires.
6. **Mixte** : autres compositions.

Le caractère intermédiaire ne dépend pas du nom de l’épreuve. Les Templiers, le Grand Raid du Finistère et l’UTMB servent de cas de vérification ; aucune règle de code ne reconnaît ces noms. Un parcours plat avec une unique grande ascension peut être classé montagne si celle-ci représente la majorité de son D+. Le détail de composition permet d’interpréter ces cas.

## Classes de distance et échantillonnage

La distance est indépendante du relief. Les bornes inférieures sont incluses.

| Profil / pas cible | < 20 km | 20–50 km | 50–100 km | 100–160 km | ≥ 160 km |
|---|---:|---:|---:|---:|---:|
| Plat | 75 m | 100 m | 150 m | 200 m | 250 m |
| Faiblement vallonné | 40 m | 50 m | 75 m | 100 m | 125 m |
| Petites bosses répétées | 25 m | 25 m | 40 m | 50 m | 60 m |
| Intermédiaire | 40 m | 50 m | 75 m | 100 m | 125 m |
| Montagne | 50 m | 75 m | 100 m | 150 m | 200 m |
| Mixte | 25 m | 40 m | 50 m | 75 m | 100 m |

Les sommets et creux significatifs sont ajoutés aux grilles. La classification demeure indépendante du pas choisi pour la prédiction. Le catalogue expose 30 combinaisons ; les groupes vides restent visibles avec leur repli explicite.

## Effet sur l’apprentissage

Les références sont d’abord regroupées par profil. Leur poids combine la proximité de distance, une préférence pour la même classe de distance et une similarité de morphologie. Cette similarité compare :

- la densité de D+ ;
- la fréquence des ascensions ;
- les parts du D+ en petites, moyennes et grandes ascensions ;
- la longueur et le gain médians des ascensions.

Le poids de similarité vaut 1 pour deux descriptions identiques et diminue avec leur différence, jusqu’à un plancher de 0,05. Les coefficients sont explicites dans `relief_similarity` de `models.py`. La faible similarité réduit aussi le support du groupe et renforce sa régularisation vers la courbe globale. Le recalage de durée selon la distance utilise les mêmes poids.

Le choix automatique conserve sa validation interne : il peut retenir le repli global si le candidat morphologique ne démontre pas un avantage suffisant. La sélection manuelle d’un groupe permet d’appliquer son candidat régularisé. Le classement des références par proximité reste calculé uniquement sur les autres courses du même profil et de la même classe de distance. Les erreurs de classement de groupe et les erreurs du mode automatique restent distinctes.

## Migration et limites

Au premier lancement, l’empreinte du code de calcul invalide les anciennes analyses et les anciens modèles. Les GPX, imports Garmin, choix d’inclusion, commentaires et scénarios enregistrés ne sont pas supprimés. Les scénarios restent des instantanés de leurs calculs précédents ; recréer un scénario est nécessaire pour utiliser le modèle 2.0. L’étiquette Git v1.3.0 conserve la version précédente.

Les quatre écrans et les fonctions existantes sont conservés : analyse, références et modèles, carte des références, comparaison/simulation, modes manuels et temps enregistrés, départs et passages, lecture, impression, exports GPX, cache, Garmin et arrêt d’import. La surveillance de validation reste active ; aucun recalcul intégral des imports personnels n’est lancé pour les essais.

La catégorisation ne modélise pas la technicité, le sol, la météo ou l’altitude physiologique. Une amélioration de précision ne peut pas être déduite de la seule création des groupes : elle doit être vérifiée par validation croisée et sur de nouvelles courses.

</details>

<a id="source-modele-2-1"></a>

<details>
<summary>MODELE-2.1.md — document source intégral</summary>

# Version 2.1 : familles de relief et consultation des références

Cette version applique les fusions demandées après les expérimentations de la version 2.0. Les autres fonctions sont conservées. Les cinq classes de distance ne changent pas.

## Quatre familles

| Famille affichée | Morphologies initiales incluses |
|---|---|
| Plat / Vallonné | Plat ou presque plat ; faiblement vallonné |
| Intermédiaire / Montagne | Relief intermédiaire soutenu ; longues ascensions de montagne |
| Dent de scie | Petites bosses répétées |
| Mixte | Relief mixte |

Les règles de détection des ascensions de la version 2.0 sont conservées. Une fois la morphologie identifiée, elle est rattachée à sa nouvelle famille. L’apprentissage, la validation par profil et les classements utilisent cette famille. Le catalogue et l’histogramme proposent donc 20 groupes.

Les indicateurs continus — densité de D+, composition, fréquence, longueur et gain des ascensions — restent propres à chaque course. La pondération peut ainsi distinguer deux parcours de la même famille. Le choix automatique et son repli global restent validés sur les références d’apprentissage.

## Pas d’analyse conservés

Le regroupement ne doit pas modifier l’échantillonnage par lui-même. Chaque parcours conserve le pas de sa morphologie initiale, stockée sous `sourceProfile`. Par exemple, un parcours Plat et un parcours Vallonné peuvent appartenir à la même famille tout en conservant leurs résolutions distinctes.

Le catalogue indique le pas minimal de la famille. Le pas réellement appliqué au parcours est affiché dans ses détails. Une sélection manuelle d’une autre famille utilise le pas de cette famille ; une sélection correspondant à la famille du parcours conserve son pas d’origine. Les anciennes clés API `rolling` et `intermediate` sont acceptées comme alias des nouvelles familles.

## Sélection dans l’histogramme

Cliquer sur une barre sélectionne sa famille et sa classe de distance. La barre est mise en évidence ; le nombre et la liste des courses incluses apparaissent sous le graphique. Le classement principal est filtré sur ce groupe. Le bouton « Ouvrir les détails » affiche l’analyse dépliée de la course dans ce classement.

Une barre est aussi accessible au clavier avec Tab, Entrée ou Espace. Sélectionner à nouveau la même barre retire le filtre. Le bouton « Afficher toutes les courses » rétablit l’ensemble du classement. Les détails déjà ouverts sont conservés lors des changements de filtre. La sélection d’un groupe vide affiche explicitement l’absence de course.

Ce filtre est uniquement visuel : il ne modifie pas les courses retenues pour l’apprentissage et ne déclenche pas de recalcul. Les cases d’inclusion dans le modèle restent le moyen de changer la sélection d’apprentissage. Avant la fin de la validation, les traces exploitables peuvent alimenter l’histogramme ; les détails complets deviennent disponibles après validation.

## Classement et détails élargis

L’écran Références utilise une largeur maximale de 1 800 px. Les colonnes ont des largeurs maîtrisées ; noms, informations de validation et détails reviennent à la ligne au lieu d’élargir la table. Les tableaux internes des branches respectent la largeur disponible. Sur un petit écran, chaque ligne de course devient un bloc de champs étiquetés, tout en conservant les branches d’analyse.

## Données et migration

Les GPX, imports Garmin, choix d’inclusion, repères et scénarios ne sont pas supprimés. La nouvelle empreinte de calcul invalide les caches précédents et déclenche la reclassification au démarrage. Les scénarios enregistrés restent des instantanés de leurs calculs antérieurs. La surveillance de validation et l’arrêt Garmin sont conservés.

Les expérimentations précédentes montraient des effets contrastés de la fusion Intermédiaire / Montagne : cette version applique le choix utilisateur et ne revendique pas un gain de précision garanti. Les mesures de l’expérience 2.0 restent dans `sorties/experiences/2026-11-08-trois-profils`.

</details>

<a id="source-validation-1-1"></a>

<details>
<summary>VALIDATION-1.1.md — document source intégral</summary>

# Validation de la version 1.1.0

Validation du 7 novembre 2026 sur Windows, Python 3.9.1 et Node.js 24.22.1.

## Vérifications automatisées

- `python -B -m unittest discover -s tests -v` : 20 tests réussis, dont les 12 tests de non-régression de la version initiale.
- `node --check src/bzhaventure/web/app.js` : syntaxe valide.
- `node tests/test_web.js` : interactions vérifiées pour le cache, les modes manuels, les repères, les réponses réseau désordonnées et la suppression filtrée.
- `git diff --check` : aucune erreur d’espacement.

Les nouveaux tests couvrent les références nouvelles, modifiées ou retirées, la réutilisation après changement de date sans changement de contenu, la corruption du cache et le refus des classes non autorisées. Ils vérifient également les durées manuelles, les repères exacts, leur chronologie et le fonctionnement sans modèle initialisé.

## Jeu complet de références

Le premier calcul avec 16 références a pris environ 60 secondes. La restauration suivante a pris 0,266 seconde et réutilisé les 16 analyses ainsi que les modèles. Ces mesures sont indicatives et dépendent de la machine.

L’erreur médiane de validation croisée du modèle courant reste de 6,319284515324458 %, identique au jalon initial. Le stockage ne change pas les règles d’apprentissage.

## Vérification dans le navigateur

Sur le parcours de 43,49 km, un départ à 07:00 et une durée totale de 10 heures produisent une arrivée à 17:00. Le repère ajouté à 12,5 km avec le commentaire « Ravitaillement en eau » apparaît sur la carte et dans le tableau. Une allure de 06:00/km produit une durée de 04:20:57. Une durée de 12:30 produit une arrivée à 19:30. L’actualisation des références restitue le cache de 16 références.

## Garmin : périmètre de validation

Le client simulé couvre connexion, MFA, types d’activités, bornes inclusives, déduplication, activités modifiées et suppression locale filtrée. Le statut de dépendance manquante est correctement affiché sur la machine Python 3.9.

La dépendance facultative exige Python 3.10 ou supérieur. Aucune connexion à un compte Garmin réel n’a été testée. Le bon fonctionnement avec un compte personnel reste à vérifier dans cet environnement compatible, selon les réponses du service Garmin. Voir [le guide d’installation](FONCTIONNEL.md#source-garmin).

## Conservation

La base locale et les activités personnelles sont exclues de Git. Les tests utilisent des bases temporaires et des données simulées. Aucun mot de passe ou jeton Garmin n’est enregistré dans le projet.

</details>

<a id="source-validation-1-2-1"></a>

<details>
<summary>VALIDATION-1.2.1.md — document source intégral</summary>

# Validation de la version 1.2.1

Le 7 novembre 2026, sur Windows avec Python 3.9.1 et Node.js 24.22.1.

- 24 tests Python réussis, dont un nouveau scénario avec deux courses courtes et une longue : la longue conserve sa prédiction automatique, mais n’a aucune estimation de classement faute de pair dans sa classe de distance. Les courtes sont validées l’une par l’autre.
- Tests web réussis : versions du ruban, import et simulation GPX autonome, résultat de 9 heures ajouté au comparatif, rangs repartant de 1 pour trois groupes distincts et absence d’étoile pour une course sans estimation de groupe.
- Syntaxe JavaScript valide et aucune erreur d’espacement détectée par Git.

Dans le navigateur, le ruban affiche « Power by BZHAventure » et « Python 3.9.1 · Application 1.2.1 ». Un GPX TRAILBELLEILE a été sélectionné depuis le nouvel écran Simulation, puis calculé pour 9 heures avec un départ le 9 novembre à 06:00 : arrivée à 15:00 et ajout effectif à la comparaison, sans passer par l’écran Analyse.

Les 16 références sont affichées sous six groupes présents dans le jeu de données. Les trois groupes de dénivelé faible, contenant chacun une course, affichent une estimation de groupe indisponible. Les groupes de relief élevé et longues portions présentent respectivement 3, 6 et 4 courses avec leurs rangs indépendants.

Le classement local apprend une courbe uniquement à partir des autres références du même profil et de la même classe de distance. Les modèles automatiques généraux et leurs indicateurs de validation restent disponibles dans la partie Modèle prédictif, distincte du classement.

</details>

<a id="source-validation-1-2-2"></a>

<details>
<summary>VALIDATION-1.2.2.md — document source intégral</summary>

# Validation 1.2.2

Le 7 novembre 2026 : 26 tests Python réussis, syntaxe JavaScript valide et tests web réussis.

Les deux nouveaux tests Python vérifient la conservation des horodatages et d’une interruption de 24 heures entre deux segments, l’interpolation d’un repère, l’accès pendant le démarrage sans modèle, et le refus d’un GPX dépourvu de dates. Des appels à `predict` et `manual_model` provoquent volontairement une erreur dans le test pour confirmer qu’ils ne sont jamais exécutés dans le mode enregistré.

Le test web importe un GPX en mode enregistré et vérifie que le résultat reprend sa durée de 1 h 20, sans transmettre les champs de durée totale ni d’allure. Un champ de départ manuel invalide n’affecte pas les dates source. Les modes prédictifs précédents restent couverts par les tests existants.

</details>

<a id="source-validation-1-2"></a>

<details>
<summary>VALIDATION-1.2.md — document source intégral</summary>

# Validation de la version 1.2.0

Validation le 7 novembre 2026, Windows, Python 3.9.1 et Node.js 24.22.1.

## Tests automatisés

- 23 tests Python réussis : les 20 précédents, plus trois tests couvrant sélection native persistante, sélection des imports, et conservation des points, segments et temps d’export.
- Tests web réussis : navigation, ajout de deux scénarios, conservation locale, écart temporel, construction du XML avec échappement des commentaires, en plus des contrôles de la version 1.1.
- Syntaxe JavaScript valide et aucune erreur de `git diff --check`.

La sélection native est testée avec fermeture/réouverture de la base et recalcul effectif du modèle sur une référence puis deux. Une clé arbitraire est refusée. Les tests utilisent des bases temporaires et ne changent pas les références personnelles.

## Vérification réelle dans le navigateur

Le parcours TRAILBELLEILE (43,49 km) a été analysé avec un départ le 8 novembre 2026 à 07:00. Deux scénarios de 10 heures et 8 heures ont été ajoutés : arrivées à 17:00 et 15:00, écart de deux heures et comparaison des repères communs.

Le scénario de 8 heures a été téléchargé par le bouton GPX, puis relu avec l’analyseur Python : 1 980 points conservés, dix repères GPX et une durée horodatée de 28 800 secondes. Les coupures de segments sont également contrôlées par un test synthétique distinct.

Le tri par proximité place UTCAM Mercantour 2021, 6666 2018 et UTMB 2017 en tête du jeu fourni. Les trois courses sont signalées comme proches du modèle. Le classement de performance est distinct et conserve ses rangs lors du changement de tri. Aucune erreur JavaScript n’a été relevée dans la console pendant ces essais.

## Limites et interprétation

L’allure par kilomètre-effort est un indicateur explicite de classement, pas une normalisation complète de la difficulté. Les modèles d’apprentissage ne changent pas dans cette version. Les scénarios figent les résultats à leur création et sont conservés dans le navigateur, dans la limite de son quota. Les comparaisons directes sont limitées au même fichier source.

L’export construit un fichier de parcours prévisionnel à partir d’une géométrie importée ; il ne crée pas de nouveaux chemins par dessin. Sans départ, aucun horodatage n’est ajouté. L’acceptation par les différents appareils GPS dépend de leurs capacités d’import et n’a pas été testée. Les prérequis et limites de l’intégration Garmin décrits dans [le guide Garmin](FONCTIONNEL.md#source-garmin) restent applicables.

</details>

<a id="source-validation-1-3"></a>

<details>
<summary>VALIDATION-1.3.md — document source intégral</summary>

# Validation de la version 1.3.0

Le 7 novembre 2026, Windows, Python 3.15.2 dans l’environnement du projet et Node.js.

## Vérifications

- 39 tests Python réussis : les 30 précédents, plus neuf tests couvrant carte des références exclues, annulation de l’import, endpoint d’arrêt indépendant du verrou de connexion, délai sans progression, durée maximale malgré des messages continus, sortie imprévue d’un processus et résultat réel de validation supervisée.
- Tests web réussis : 16 barres et quatre entrées de légende, navigation vers la carte, tracé SVG de secours, liste des références, retour d’arrêt Garmin et message de surveillance.
- Syntaxe JavaScript valide et aucune erreur d’espacement détectée par Git.

Le test de blocage arrête le processus enfant puis vérifie qu’aucun processus de validation supplémentaire ne reste actif. Les délais de test sont volontairement courts ; ceux de production restent 180 secondes sans progression et 1 800 secondes au total.

## Vérification réelle

La validation complète des 16 exemples fournis aboutit dans le processus surveillé. Une base QA séparée des imports personnels a été utilisée pour cette vérification.

Dans le navigateur, l’histogramme présente les effectifs attendus : dénivelé faible `[1, 1, 0, 1]`, longues montées/descentes `[0, 3, 6, 4]`, et zéro pour les deux autres profils. La carte affiche les 16 courses, leurs marqueurs et les traces sur un fond OpenStreetMap. Aucune erreur JavaScript n’a été relevée pendant ces essais.

Le test d’arrêt Garmin simule un arrêt après le premier enregistrement et vérifie qu’un seul téléchargement est effectué, que cette activité reste stockée et que le bilan porte `cancelled=true`. Un second test interrompt la pagination avant les téléchargements. Aucun import sur un compte Garmin réel n’a été lancé pour ces essais.

## Limites

La surveillance concerne la validation et la construction des modèles ; la lecture initiale des GPX et les accès SQLite ne s’exécutent pas dans ce processus. Une requête réseau Garmin en cours doit se terminer avant que son arrêt soit pris en compte. Le traitement d’un grand jeu de références peut dépasser les limites et être interrompu : réduire la sélection puis relancer permet de contrôler la charge. L’ensemble des 381 imports alors retenus dans la base personnelle n’a pas été validé intégralement pendant cette vérification.

</details>

<a id="source-validation-2-0"></a>

<details>
<summary>VALIDATION-2.0.md — document source intégral</summary>

# Validation de la version 2.0.0

Le 8 novembre 2026, Windows, Python 3.15.2 et Node.js.

## Vérifications automatisées

- 48 tests Python réussis, dont les contrôles existants du cache, de Garmin/MFA et de son annulation, des modes enregistrés/manuels, de l’export, de la carte et du superviseur de validation.
- Neuf nouveaux tests couvrent les cinq classes de distance et leurs bornes, deux formes de relief à densité de D+ comparable, le bruit d’altitude, les six profils et leur composition, une longue montée de gain modéré, les ruptures GPX, l’indépendance au pas de prédiction, les poids de similarité et les 30 groupes de catalogue.
- Tests web adaptés à 30 groupes et cinq couleurs de distance : navigation, graphiques, comparaison, saisies, réponses concurrentes, export et arrêts restent couverts.
- Syntaxe JavaScript et vérification des espaces Git valides.

Les anciens profils synthétiques ont été adaptés aux nouveaux seuils explicites. Les vérifications de calendrier, intégration des durées, pauses et API ont été conservées.

## Essai complet sur les 16 GPX fournis

La reclassification et la validation croisée complète ont abouti dans le processus surveillé, sur une base QA séparée des imports personnels.

| Mesure | Résultat |
|---|---:|
| Erreur absolue médiane du mode automatique 2.0 | 6,8231469579 % |
| Erreur absolue moyenne du mode automatique 2.0 | 9,7906733160 % |
| Erreur médiane de la référence historique à 100 m | 7,4647221358 % |
| Erreur médiane de la version précédente sur les mêmes 16 exemples | 6,3192845153 % |

La version 2.0 n’améliore donc pas la précision médiane du jalon précédent sur cet échantillon : elle augmente d’environ 0,50 point de pourcentage. Elle applique la nouvelle description du relief et ses pondérations, sans prétendre à un gain global démontré. Les seuils et coefficients devront être évalués sur des données supplémentaires, sans se contenter de les ajuster sur ces 16 courses.

Le modèle automatique conserve son repli global si le candidat de groupe n’apporte pas un avantage suffisant en validation interne. La « référence historique à 100 m » affichée dans l’application est le modèle initial, pas le résultat de la version 1.3.

## Classification observée

| Course | Profil 2.0 |
|---|---|
| Grand raid du Finistère 2023 | Petites bosses répétées / côtier |
| Belle Ile en Trail 2021 | Petites bosses répétées / côtier |
| Trail du bout de Monde 2025 | Petites bosses répétées / côtier |
| Endurance Trail Templiers 2016 | Relief intermédiaire soutenu |
| LESTEMPLIERS 2026 | Relief intermédiaire soutenu |
| UTMB 2017 | Longues ascensions de montagne |
| Lavaredo Ultra Trail 2022 | Relief mixte |
| XGTV 2022 Full | Relief mixte |

Au total : trois profils côtiers, six intermédiaires, cinq de montagne et deux mixtes. Aucun parcours plat ou faiblement vallonné n’est présent dans ce jeu de 16 références ; ces catégories sont couvertes par les tests synthétiques et pourront être alimentées par les imports.

Le seuil de séparation des ascensions est de 10 m. La catégorie des petites ascensions repose sur le gain inférieur à 100 m ; pour classer une course en profil côtier, la longueur médiane des petites ascensions doit être au plus égale à 1 km. Cela évite qu’une limite stricte appliquée à chaque petite montée déforme la classification à cause de quelques portions côtières plus longues.

## Vérification dans le navigateur

Le catalogue et l’histogramme affichent 30 combinaisons. Les nouvelles classes sont disponibles dans la sélection des modèles et dans les groupes du tableau des références.

Une prédiction automatique du parcours TRAILBELLEILE, sur les 16 références QA, produit 06:53:37 pour 43,49 km. Elle est classée « Petites bosses répétées / côtier », dans la classe 20–50 km ; les détails affichent 17,3 m de D+ lissé par kilomètre, 6,2 ascensions par 10 km, un gain médian de 25 m et une longueur médiane de 0,62 km. Pour cet essai, la validation interne retient le repli global. Aucune erreur JavaScript n’a été observée pendant ces vérifications.

## Conservation et limites

Les imports personnels, choix de références et scénarios ne sont pas supprimés. Les scénarios existants conservent leurs anciennes prévisions. Le premier démarrage en 2.0 invalide les caches de calcul et réanalyse les références actives. Les limites du superviseur s’appliquent toujours aux validations volumineuses ; les 381 imports retenus dans la bibliothèque personnelle n’ont pas été validés intégralement pendant cet essai.

La morphologie ne décrit pas la technicité du terrain, les conditions météorologiques ou l’effet physiologique de l’altitude. Les seuils restent des règles métier propres à l’application.

</details>

<a id="source-validation-2-1-2"></a>

<details>
<summary>VALIDATION-2.1.2.md — document source intégral</summary>

# Validation 2.1.2

Le 8 novembre 2026. Modification limitée au plein écran de la carte des références.

La syntaxe JavaScript et les tests web passent. Les nouveaux scénarios couvrent l’entrée et la sortie via l’API native simulée, le repli en panneau agrandi si l’API est refusée, la sortie par Échap, le libellé et l’état aria-pressed du bouton, et la restauration du défilement de page.

Dans le navigateur de test, l’API native est refusée et le panneau agrandi prend le relais. La carte mesure alors 589 px de haut dans une fenêtre de 720 px ; le filtre et les commandes restent visibles. La sortie par le bouton rétablit l’état normal. Les données sont celles de la base QA séparée, sans accès à un compte Garmin réel.

Les calculs et les modèles ne sont pas modifiés par cette version.

</details>

<a id="source-validation-2-1-3"></a>

<details>
<summary>VALIDATION-2.1.3.md — document source intégral</summary>

# Validation 2.1.3

57 tests Python réussis et contrôles Node du contrôleur web réussis le 8 novembre 2026. Les tests couvrent les filtres combinés, la cohérence liste/suppression, le cache de classification et son invalidation, les GPX invalides et un import Garmin simulé. Le démarrage sur la base QA séparée atteint 100 %. La connexion Garmin réelle et la vérification visuelle dans un navigateur ne sont pas couvertes par cette validation.

</details>

<a id="source-validation-2-1"></a>

<details>
<summary>VALIDATION-2.1.md — document source intégral</summary>

# Validation de la version 2.1.0

Le 8 novembre 2026, Windows, Python 3.15.2 et Node.js.

## Calculs et non-régression

52 tests Python réussis. Les quatre nouveaux tests vérifient les deux fusions, la conservation de la morphologie initiale et de son pas, les noms Dent de scie et Mixte, le pas réellement utilisé en prédiction et les anciennes clés de sélection API. Le catalogue contient désormais 20 combinaisons, avec les cinq classes de distance conservées.

Les tests existants couvrent les caches, le classement par groupe, la validation surveillée et son arrêt, Garmin et son annulation, les horaires, les modes manuels/enregistrés et les exports GPX. Les tests de classification ont été adaptés aux quatre familles sans supprimer les contrôles des caractéristiques morphologiques.

## Histogramme

Les tests web vérifient les 20 barres, la sélection d’un groupe, la liste de ses courses, le filtre du classement, l’ouverture des détails et le rétablissement de la liste. Ils vérifient aussi l’accès clavier, les groupes vides et la conservation d’une branche ouverte après retrait du filtre.

Dans le navigateur, la sélection Intermédiaire / Montagne, 100–160 km, sur le jeu QA de 16 références, affiche cinq courses : Maxi Race, Endurance Trail Templiers, MIUT, LESTEMPLIERS et TDS. Le bouton de détails ouvre correctement une branche. La réinitialisation restitue les 16 références et conserve cette branche ouverte. La sélection clavier d’un groupe vide affiche explicitement zéro course.

## Largeur du classement

À une largeur de fenêtre de 1 280 px, le conteneur du classement mesure 1 179 px et son contenu ne dépasse pas cette largeur. Après ouverture des détails puis rétablissement de toutes les références, aucun tableau visible du classement ou de la branche n’a de largeur défilante supérieure à sa largeur disponible. La page ne présente pas de débordement horizontal.

Les règles CSS ajoutent une présentation en blocs étiquetés sous 760 px ; cette présentation n’a pas fait l’objet d’un essai sur appareil mobile physique. La mesure réelle ci-dessus concerne le navigateur de bureau.

## Limites et conservation

La validation complète et la vérification visuelle utilisent une base QA distincte des imports personnels. Les 42 références personnelles n’ont pas été recalculées dans la base active pendant ces essais. Le premier démarrage de l’installation mettra à jour ses analyses et modèles selon les nouvelles familles, sous la surveillance existante.

Les expérimentations précédentes avaient montré des effets contrastés pour la fusion Intermédiaire / Montagne. Cette version applique les deux fusions explicitement demandées et ne revendique pas une amélioration de précision garantie. Les cinq classes de distance, les pas des morphologies initiales, les indicateurs continus, les GPX, imports, choix d’inclusion et scénarios sont conservés.

La syntaxe JavaScript et les tests web sont valides. Aucune erreur JavaScript n’a été observée lors de la vérification du navigateur.

</details>

<a id="source-validation-2-2"></a>

<details>
<summary>VALIDATION-2.2.md — document source intégral</summary>

# Validation 2.2.0

Le 8 novembre 2026 : 61 tests Python réussis et contrôles Node du contrôleur web réussis.

Couverture ajoutée : conservation des points (y compris stationnaires), segments, altitudes, horaires et repères ; conservation des capteurs en mode compact et retrait en mode allégé ; absence d’invention des horaires ; refus des documents invalides ; conversion HTTP suivie d’une comparaison enregistrée ; bilan et téléchargement dans le contrôleur web simulé.

Essai local sur le GPX Endurance Trail templiers 2026 : source 26 190 985 octets et 64 292 points ; compactage 21 111 867 octets (19,4 %, encore au-dessus de 20 Mio) ; allègement 11 363 713 octets (56,6 %, importable). Les deux résultats restent compatibles avec les horaires enregistrés. Source originale vérifiée inchangée. Traitement mesuré autour de 5 secondes par mode sur ce poste ; ce temps n’est pas une garantie pour d’autres fichiers.

Les tests HTTP utilisent un gestionnaire et des flux locaux, sans compte Garmin ni bibliothèque utilisateur. Les contrôles web utilisent un DOM simulé ; le rendu visuel et le téléchargement dans un navigateur réel ne sont pas couverts.

</details>

<a id="source-validation-2-3"></a>

<details>
<summary>VALIDATION-2.3.md — document source intégral</summary>

# Validation 2.3.0

Le 8 novembre 2026 : 62 tests Python réussis ; contrôles Node du contrôleur web réussis.

Les contrôles ajoutés couvrent le filtre du catalogue de modèles, la fermeture et la réactivation de l’assistant, la navigation Conversion, la lecture commune sur des durées différentes, le positionnement intermédiaire, le maintien pendant une coupure de segments, le changement de vitesse et de coloration sans modification des données, le retrait d’un run, les sections chronométrées sur la grille de relief et le prévisualisateur HTTP du fichier source.

Vérification dans le navigateur sur un serveur QA séparé : affichage initial du guide, désactivation conservée après rechargement, sélection d’un modèle avec une seule ligne visible, import groupé des Templiers 2016 et 2026 en mode allégé, tableau avec horaires d’origine distincts, cartes Leaflet et profils côte à côte, lecture/pause et déplacement commun des positions, changement de coloration en altitude. Les deux courses ont la même horloge de lecture avec des distances parcourues différentes. Les gros scénarios sont restaurés après rechargement grâce à IndexedDB. La conversion expose les informations et la carte du fichier source.

Les traces sources et la base utilisateur ne sont pas modifiées. Le fonctionnement sans fond cartographique est couvert par le contrôleur DOM simulé, et non par une panne réseau provoquée dans le navigateur. La carte en ligne dépend de Leaflet/OpenStreetMap. La qualité des données GPX et les capacités de stockage du navigateur restent des limites externes.

</details>

<a id="source-validation-2-4-1"></a>

<details>
<summary>VALIDATION-2.4.1.md — document source intégral</summary>

# Validation 2.4.1

68 tests Python réussis et contrôles Node du contrôleur web réussis le 8 novembre 2026. Les contrôles ciblés vérifient l’envoi des réglages dans la requête Analyse et leur absence dans les imports directs de Simulation, qu’ils soient manuels ou enregistrés.

Vérification dans le navigateur sur la base QA séparée : bloc Stratégie d’allure du parcours visible dans Analyse avant Calculer le parcours et absent de Simulation ; import des Templiers 2016 avec durée 10 h, ajustement −10 % et split négatif de 10 %, résultat 9 h ; Ajouter l’analyse actuelle conserve le résultat et le libellé de stratégie dans la comparaison. Capture après rechargement pour vérifier le placement définitif. Les fichiers source et la bibliothèque utilisateur restent intacts.

</details>

<a id="source-validation-2-4"></a>

<details>
<summary>VALIDATION-2.4.md — document source intégral</summary>

# Validation 2.4.0

Le 8 novembre 2026 : 68 tests Python réussis et contrôles Node du contrôleur web réussis.

Tests ajoutés : ajustement neutre, pourcentages de durée signés, splits par moitié de distance sur un terrain asymétrique, conservation de la durée par le split seul, découpage exact d’une section à mi-distance, réglage des montées, combinaison des multiplicateurs, cohérence des repères et exports, non-mutation de l’estimation source, refus des réglages invalides et des stratégies sur temps enregistrés. Un appel HTTP manuel de 7 200 secondes ajusté à −10 % produit 6 480 secondes jusqu’au dernier point exporté.

Le contrôleur web vérifie les paramètres envoyés, la désactivation des stratégies en mode enregistré, le cadrage sur les seules coordonnées de la course sélectionnée et la fiche d’informations. Le libellé Dents de scie est vérifié sur la classification et sur un ancien scénario affiché.

Navigateur sur la base QA distincte : thème côtier affiché ; sélection des Templiers 2016 par le sélecteur, fiche distance/D+/D−/durée/horaires/pauses et cadrage du parcours ; simulation réelle de ce GPX avec durée initiale 10 h, split négatif de 10 %, ajustement global −10 % et montée 0 %, résultat 9 h et variation finale −10 %. Aucune erreur de console observée pendant cet essai.

Les modifications ne concernent ni les GPX source ni la base utilisateur. Les stratégies sont des scénarios et ne changent pas les modèles appris. Le changement de libellé dans les paramètres peut invalider le cache et provoquer un recalcul au premier démarrage. Les tests numériques constituent des vérifications de cohérence, pas une mesure de précision sportive des stratégies.

</details>

<a id="source-validation-3-0"></a>

<details>
<summary>VALIDATION-3.0.md — document source intégral</summary>

# Validation PrédicTrail 3.0.0

74 tests Python et contrôles Node réussis le 8 novembre 2026. Les nouvelles vérifications couvrent l’archive complète, les empreintes, les chemins interdits, la conservation des scénarios, la sélection remappée sur un nouveau dossier, la copie de sécurité et le retour arrière lors d’une erreur de remplacement. Le contrôleur charge également backup.js et vérifie les commandes et réglages sauvegardés sans identifiant Garmin.

Le paquet Windows x64 est construit avec Python 3.15.2, PyInstaller 6.22.3 et les dépendances verrouillées dans requirements-windows.lock. Autotest du binaire : interface et logo présents, trois exemples fictifs, Garmin disponible, données dans un dossier de test séparé. Le serveur autonome démarre, construit les modèles dans un processus isolé et atteint 100 %. Un test HTTP sur ce binaire crée, télécharge, inspecte et restaure une sauvegarde réelle de cinq fichiers et un scénario ; l’état après restauration est identique. Le test refuse toute instance dont les références ne sont pas toutes fictives.

La version autonome est également ouverte dans le navigateur : nom PrédicTrail, analyse d’un GPX fictif avec stratégie, ajout du scénario, création d’une archive et aperçu de restauration. Le compte Garmin réel n’est pas connecté. Les références et la base personnelles ne sont pas utilisées pour ces vérifications.

Le paquet contient uniquement l’application, ses dépendances et trois démonstrations synthétiques. La publication GitHub part d’une copie de sources sans historique local et sans GPX personnels. La signature de l’exécutable et le test sur une deuxième machine physique restent à réaliser avant une diffusion élargie.

La sauvegarde automatique a été vérifiée sur un second dossier isolé : archive quotidienne et marqueur de journée créés. La reprise du dernier GPX après restauration a également été vérifiée dans le navigateur. Une sauvegarde initiale des données serveur personnelles a été créée par copie SQLite sans modifier la base originale ; les anciens scénarios du navigateur devront être repris lors de la première ouverture de la nouvelle version. La publication GitHub reste conditionnée à l’autorisation d’écriture de l’intégration pour pr-dicTrail (refus 403 constaté).

</details>

<a id="source-validation"></a>

<details>
<summary>VALIDATION.md — document source intégral</summary>

# Validation du jalon 1.0.0

Validation effectuée le 7 novembre 2026 sur le projet organisé.

## Vérifications de réorganisation

- 34 fonctions et classes de calcul comparées structurellement aux sources validées, après retrait des seules chaînes de documentation.
- JavaScript comparé au contrôleur d'origine après retrait des commentaires ajoutés.
- Règles CSS comparées après mise en forme.
- Logo, 16 références et trois parcours d'exemple comparés aux fichiers d'origine.
- Imports des modules et aide de la commande de prédiction vérifiés.
- Liens locaux des guides vérifiés.

## Tests de non-régression

Les 12 tests Python ont réussi. Ils couvrent les quatre profils de relief, les traces courtes, les horodatages requis pour les références, les intervalles adaptatifs, les repères et la chronologie, les groupes non représentés, le type du modèle expérimental, les pauses et interruptions, les fichiers web, l'état de démarrage et une réponse de prédiction complète.

La syntaxe du contrôleur JavaScript a été vérifiée avec Node.js.

~~~powershell
python -B -m unittest discover -s tests -v
node --check src/bzhaventure/web/app.js
~~~

## Validation complète des références

L'initialisation complète a atteint l'état prêt avec 16 références et 16 groupes de modèles. Le temps observé pour cette exécution était de 64,9 secondes.

| Mesure | Modèle actuel | Candidat par inclinaison |
|---|---:|---:|
| Erreur absolue médiane | 6,3192845153 % | 7,2629616473 % |
| Erreur absolue moyenne | 9,7226205661 % | 10,3460237224 % |

Les erreurs médianes correspondent aux résultats de la version validée avant réorganisation, avec une tolérance de comparaison de 10⁻⁹ point de pourcentage.

Chaque course est exclue de son apprentissage lors du calcul des erreurs. La validation interne du choix de modèle est réalisée sur les références restantes.

## Portée

Ces résultats vérifient le comportement de calcul et le conditionnement des ressources locales. La vérification visuelle de l'impression dépend également du navigateur et du chargement du fond cartographique. Le guide technique fournit le parcours de vérification visuelle à rejouer après une évolution de l'interface.

</details>
