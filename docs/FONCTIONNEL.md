# Guide fonctionnel

## Objectif et périmètre

BZHAventure UltraTrail estime le temps total et les temps de passage d'un parcours à partir de courses déjà réalisées. Les références alimentent les modèles d'allure selon la pente, la distance et le type de relief.

La version 2.1.2 comprend un tableau de bord web local et une commande de génération de rapport HTML. Le tableau de bord constitue l'interface principale.

## Données d'entrée

| Donnée | Utilisation | Conditions |
|---|---|---|
| GPX de référence | Apprentissage et validation | Coordonnées, altitudes et horodatages ordonnés |
| GPX à prédire | Géométrie et caractéristiques du parcours | Coordonnées et altitudes |
| Date et heure de départ | Dates civiles des passages et de l'arrivée | Facultatives, dans le fuseau de l'appareil |
| Espacement des repères | Carte et tableau des passages | De 1 à 50 km |
| Choix du modèle | Courbe d'allure et échantillonnage appliqués | Automatique, global, groupe ou expérimental |

Les pistes et leurs segments sont pris en charge. Les routes GPX sont utilisées en l'absence de piste exploitable. Les références invalides sont écartées avec leur motif. Un fichier importé dans le navigateur est limité à 20 Mo.

L'application exploite les horodatages des références. Le parcours à prédire peut être dépourvu d'horodatage.

## Démarrage

Lancer `python lancer.py`, puis ouvrir l'adresse locale affichée.

La page présente une barre d'avancement avec les phases suivantes.

1. Lecture, classification et analyse des références.
2. Validation de chaque course et test des classes d'inclinaison.
3. Construction du catalogue des modèles.
4. Mise à disposition de l'analyse du parcours.

La phase, la course traitée, le compteur et le temps écoulé sont visibles. Une erreur de démarrage est affichée dans la page et dans le terminal. Les commandes d'importation deviennent disponibles lorsque les résultats sont prêts.

## Analyse d'un parcours

Choisir un modèle, puis utiliser le bouton de sélection du GPX.

Le récapitulatif affiche le nom et la taille du fichier, le nombre de points et de segments, la distance, les dénivelés positif et négatif, le temps total, le temps hors pauses et les pauses estimées. Si un départ est renseigné, l'arrivée prévue apparaît également.

La modification du modèle relance l'analyse du fichier sélectionné. La modification de l'espacement des repères met à jour les passages. La classification du parcours et le modèle effectivement appliqué sont affichés, y compris lorsqu'un modèle de repli est utilisé.

## Départ et horaires

La date de départ est exprimée dans le fuseau horaire de l'appareil, indiqué à côté du champ.

Les horaires sont calculés en ajoutant les durées cumulées à l'instant de départ. Le calcul prend en compte les passages à minuit et les changements d'heure. Une heure locale inexistante lors du passage à l'heure d'été est signalée.

Les horaires se mettent à jour lors de la saisie. Le bouton de recalcul permet de les actualiser explicitement. L'effacement du départ retire les dates civiles calculées.

Une heure répétée lors du passage à l'heure d'hiver est interprétée selon le choix du moteur de date du navigateur. La version 1.0.0 ne propose pas de choix manuel d'offset pour cette ambiguïté.

## Carte et profil

La carte affiche le parcours et les repères, avec leur distance et leur date de passage lorsque le départ est renseigné. Un clic sur un repère donne ses informations détaillées.

La coloration peut représenter la pente, l'altitude ou la vitesse moyenne prédite. Le profil altimétrique utilise les mêmes règles et la même échelle de couleurs.

Le plein écran conserve les commandes de lecture, le curseur de position, la vitesse et les informations de suivi. Les commandes permettent de lire, mettre en pause, revenir au départ et se déplacer directement dans le parcours. Le multiplicateur de lecture va de ×60 à ×7200.

La position, l'altitude, la durée écoulée et la date de passage évoluent ensemble. La carte et le profil partagent la même chronologie.

Le tracé SVG de secours conserve le parcours, les repères et le suivi si Leaflet est indisponible. Le fond OpenStreetMap nécessite une connexion.

## Tableau des passages

Chaque ligne indique le repère, la distance, le temps total cumulé, la date et l'heure de passage, l'altitude, le terrain dominant depuis le repère précédent et les pauses cumulées estimées.

Le terrain dominant correspond à la plus grande distance couverte en montée, sur le plat ou en descente sur l'intervalle. Le plat couvre les pentes de −3 % à +3 %, bornes incluses. Les flèches indiquent ↗ montée, → plat et ↘ descente.

Le départ et l'arrivée sont inclus, même si la distance finale n'est pas un multiple de l'espacement choisi.

## Références et arborescence

Chaque course de référence se déplie dans la liste. Les branches présentent le profil, les résultats par terrain, les pauses et interruptions d'enregistrement, ainsi que sa classification et son échantillonnage.

Le tableau compare le temps GPX au temps estimé en retirant cette course des références d'apprentissage. Les résultats du candidat par classes d'inclinaison sont également consultables.

## Classification et échantillonnage

La version 2.0 distingue cinq classes de distance : moins de 20 km, 20 à moins de 50 km, 50 à moins de 100 km, 100 à moins de 160 km et 160 km ou plus.

Les familles sont : Plat / Vallonné, Intermédiaire / Montagne, Dents de scie et Mixte. Les six morphologies initiales restent utilisées pour décrire les parcours et conserver leurs pas d’analyse. Le calcul utilise une grille commune de 25 m, un lissage médian et un seuil d’inversion de 10 m. Il décrit séparément densité de D+, longueur, amplitude et fréquence des ascensions ainsi que leur répartition. Les règles détaillées et les pas d’échantillonnage figurent dans [le guide du modèle 2.0](MODELE-2.0.md).

Les détails des références et de la prédiction affichent ces indicateurs. Les classements et l’histogramme utilisent les 20 groupes famille–distance. L’histogramme est sélectionnable et donne accès aux courses du groupe. Les autres écrans et fonctions sont conservés.

## Choix du modèle et validation

Le mode automatique choisit le groupe du parcours. Le candidat du groupe combine les références du même profil, leur proximité de distance et de morphologie du relief, ainsi qu’une courbe globale. La part locale est réduite quand le groupe manque de références.

Avec au moins trois références du profil, une validation interne compare le candidat au modèle global historique. Le candidat doit améliorer l'erreur moyenne au-delà d'une marge égale à une erreur standard des écarts appariés. Le choix est fait sur les seules données d'apprentissage de chaque pli.

Le mode global applique la courbe globale pondérée. Un choix manuel de groupe applique sa courbe candidate et son pas cible. Un groupe sans données suffisantes utilise un repli indiqué à l'écran.

Le catalogue présente les 16 groupes, leur courbe, les références du groupe et les erreurs du mode automatique. Les erreurs affichées pour un groupe ne constituent pas une mesure propre à un choix manuel forcé.

## Variante expérimentale par inclinaison

Cette variante utilise onze classes. Elle distingue le plat et cinq niveaux de pente dans chaque sens, délimités par 3, 8, 15, 25 et 40 %. Les classes peu documentées s'appuient sur le modèle historique.

Le tableau de test affiche les distances testées et les écarts cumulés par pente. Des erreurs de sens opposé peuvent se compenser dans ces cumuls.

Sur les 16 références du jalon 1.0.0, la validation a produit les résultats suivants.

| Modèle | Erreur absolue médiane | Erreur absolue moyenne |
|---|---:|---:|
| Historique, grille de 100 m | 7,5 % | 9,7 % |
| Actuel avec sélection validée | 6,3 % | 9,7 % |
| Expérimental par inclinaison | 7,3 % | 10,3 % |

Ces mesures décrivent le jeu de références fourni. L'ajout ou le remplacement de références modifie les résultats.

## Pauses

Une pause observée est une période continue d'au moins une minute à une vitesse inférieure ou égale à 0,5 km/h sur les points GPX d'origine.

Les intervalles de plus de cinq minutes et les coupures entre segments sont comptés séparément comme interruptions d'enregistrement. Le temps de pause réel pendant ces interruptions reste inconnu.

L'estimation des pauses du parcours utilise les ratios observés dans les références, pondérés par leur couverture et, selon le modèle, par le groupe. Le temps total appris inclut déjà les pauses. L'application le décompose en temps hors pauses et pauses estimées.

Les pauses cumulées aux repères sont réparties proportionnellement au temps prévu. Les lieux et durées d'arrêts individuels ne sont pas planifiés par cette version. Une estimation indisponible est affichée avec un tiret.

## Impression

Le bouton d'impression prépare le fichier analysé, le récapitulatif, le modèle appliqué, la carte entière avec repères, le profil et le tableau des passages.

La lecture est mise en pause. Le cadrage est ajusté pour l'impression, puis restauré. Le navigateur permet de choisir une imprimante ou d'enregistrer en PDF. Le chargement du fond cartographique dépend de la connexion et du navigateur.

## Gestion des données

Les références sont stockées dans `data/references`. Les parcours de démonstration sont dans `data/parcours`.

Un GPX importé par la page est traité en mémoire pour la requête. Les résultats restent dans la page ouverte. Pour recalculer les modèles après une modification des références, redémarrer le serveur.

Le dépôt Git conserve les sources, les données fournies, les documents et les archives. Il s'agit d'un versionnement local.

## Limites d'interprétation

La précision dépend des références, de leurs horodatages et de la qualité des altitudes GPS. La classification utilise des seuils explicites. Les groupes peu représentés restent incertains.

La météo, l'état du terrain, la technicité, les barrières horaires, la nutrition et l'état de forme du jour ne font pas l'objet de variables dédiées dans cette version. Le dénivelé affiché est calculé sur l'échantillonnage retenu. La vitesse prédite correspond à une moyenne temporelle intégrant la part de pauses du modèle.

## Nouveautés 1.1 : bibliothèque et cache

Les analyses des références et les modèles calculés sont conservés localement dans SQLite. Au démarrage, les fichiers inchangés sont reconnus par leur taille et leur date de modification, sans relecture du GPX. Si ces métadonnées changent, une empreinte du contenu détermine si une nouvelle analyse est nécessaire. Une modification du code de calcul ou de version Python invalide les résultats calculés. La validation des modèles est relancée lorsque l’ensemble des références change. Un cache endommagé est recalculé. Une modification conservant volontairement taille et date de fichier ne peut pas être détectée par ce contrôle rapide.

Ajouter un GPX chronométré dans la bibliothèque depuis l’interface, ou déposer le fichier dans `data/references` puis cliquer sur l’actualisation. La liste des imports permet d’inclure ou d’exclure chaque activité des références. Les doublons de contenu sont ignorés. Une progression indique l’import et le recalcul ; le nouvel ensemble de modèles est publié une fois cohérent.

## Horaires sans modèle

Le choix de méthode propose le modèle appris, une durée totale au format heures:minutes[:secondes], ou une allure au format minutes:secondes par kilomètre. Cliquer sur « Calculer le parcours » après saisie. Les deux modes manuels appliquent une allure constante à la distance, indépendamment de la pente. Ils sont utilisables avant la fin de l’initialisation des références. Les pauses éventuelles doivent être comprises dans la durée ou l’allure saisie ; aucune pause apprise n’est ajoutée. La date et l’heure de départ déterminent les passages et l’arrivée.

## Repères personnalisés

Saisir la distance cumulée depuis le départ en kilomètres et un commentaire facultatif, puis ajouter le repère. Il apparaît dans le tableau et sur la carte, avec son horaire. Les repères sont triés avec les repères réguliers ; un même kilomètre est fusionné pour éviter les doublons. Ils peuvent être retirés individuellement. Une distance hors du parcours est refusée. Le changement de fichier efface la liste associée au parcours précédent.

## Import Garmin

Consulter le [guide Garmin](GARMIN.md) pour les prérequis, les filtres de sélection, la conservation et la suppression locale. Les données importées restent disponibles hors connexion.

## Version 1.2 : navigation en trois écrans

1. **Analyse d’un parcours** : importer la trace à prévoir, régler méthode, date de départ et repères, consulter carte et horaires, imprimer ou exporter le GPX.
2. **Courses de référence et modèle prédictif** : importer un GPX chronométré pour l’apprentissage, sélectionner les fichiers, consulter leur classement et les courbes. La bibliothèque Garmin se trouve dans cet écran.
3. **Simulation et comparaison de runs** : nommer et ajouter le résultat de l’analyse courante, puis revenir au premier écran pour modifier un paramètre et ajouter un nouveau scénario.

### Classement et sélection des références

La liste « Sélectionner les courses à prendre dans le modèle » contient les références fournies et les imports, y compris les courses exclues. Cocher ou décocher déclenche l’actualisation du modèle ; le choix est conservé dans SQLite. Les fichiers originaux sont conservés. Si toutes les références sont exclues, les calculs appris deviennent indisponibles ; les modes manuels et la liste de sélection permettent de continuer et de réactiver une référence.

Le classement de performance utilise `durée / (distance en km + D+/100)`, exprimé en temps par km-effort : plus il est bas, plus la performance selon cet indicateur est élevée. Ce repère ne corrige pas la météo, la technicité ou la fatigue. Le rang repart de 1 dans chaque groupe de profil et de classe de distance et reste indépendant de la proximité au modèle. Les tris par distance, nom et erreur absolue sont également disponibles.

Dans chaque groupe de profil et de classe de distance, les trois courses dont l’écart absolu entre temps réel et temps prédit est le plus faible sont signalées en vert et par une étoile. Chaque prédiction de classement apprend sa courbe exclusivement à partir des autres courses du même groupe. Aucun repli sur le modèle global n’est utilisé pour ce classement. Cette mise en évidence exprime une proximité relative au sein du jeu sélectionné, sans garantir un seuil de qualité. Une course seule ne possède pas de prédiction de validation.

### Construction et export du GPX

Le bouton « Exporter le parcours GPX » produit un GPX 1.1 à partir de la trace analysée. Les coordonnées et altitudes d’origine ainsi que les coupures de segments sont conservées. Les repères réguliers et personnalisés deviennent des points GPX `wpt`, avec leur libellé et commentaire. Le nom de course est repris dans les métadonnées et la trace.

Quand un départ est renseigné, chaque point reçoit un horaire UTC calculé avec le modèle ou l’allure choisie. Sans départ, le GPX reste géographique sans horodatage inventé. Les dates des points exportés sont prévisionnelles : un GPX de prédiction ne doit pas servir de référence d’une performance réellement courue. Les lieux et durées d’arrêts individuels ne sont pas modélisés ; la répartition temporelle reste celle de l’analyse. La création d’une géométrie par dessin sur carte ne fait pas partie de cette version.

### Comparaison des scénarios

Chaque run fige le résultat de l’analyse et son départ au moment de l’ajout. Les modifications ultérieures et les recalculs du modèle ne modifient pas les runs enregistrés. Le tableau compare durée, départ, arrivée et écart au premier run. Le graphique compare les durées totales. Un second tableau montre temps cumulés et horaires des repères présents à la même distance sur les scénarios issus du même fichier GPX. Un repère absent est indiqué explicitement.

Les écarts directs ne sont affichés que pour le même fichier source ; les parcours différents sont identifiés. Le changement de nom de scénario n’altère pas le parcours. Chaque run peut être retiré ou exporté individuellement en GPX. Les 20 scénarios maximum sont sauvegardés dans le stockage de ce navigateur pour cette adresse locale ; ils ne sont pas partagés entre navigateurs ou ports. Si le stockage est refusé ou plein, un message signale leur conservation uniquement pour la session. Effacer les données du navigateur efface ces scénarios.

## Correctifs 1.2.1

Le ruban affiche « Power by BZHAventure », la version de l’interpréteur Python qui exécute le serveur et la version de l’application.

Dans Simulation, cliquer sur « Importer des GPX à simuler », sélectionner un ou plusieurs fichiers puis choisir la méthode : modèle appris (avec sélection du modèle), durée totale ou allure min/km. Saisir éventuellement un départ, régler les repères et cliquer sur « Simuler les GPX et ajouter à la comparaison ». Ces paramètres sont indépendants de ceux de l’écran Analyse ; une durée ou allure imposée s’applique à chacun des fichiers sélectionnés. Un préfixe de nom facultatif est repris pour chaque run. La progression et les erreurs sont affichées par fichier ; les résultats réussis sont conservés même si un autre fichier échoue. La limite totale reste de 20 runs. Les modèles appris exigent une initialisation terminée ; les modes manuels restent disponibles pendant le démarrage.

Le tableau des références affiche un en-tête pour chaque profil et classe de distance. Le classement de performance, le tri par proximité et les étoiles sont calculés séparément dans chacun de ces groupes. La colonne « Estimé · groupe » et la métrique « Erreur médiane · groupes » utilisent les prédictions sans la course évaluée, entraînées sur les seuls pairs du même groupe. Une référence sans pair exploitable affiche une estimation indisponible et ne reçoit pas d’étoile de proximité. Les courbes et indicateurs de validation générale du modèle, dans la partie dédiée, restent distincts de ce classement.

## Version 1.2.2 : comparaison sans prédiction

La méthode par défaut de l’écran Simulation est « Temps enregistrés du GPX · sans prédiction ». Importer un ou plusieurs fichiers puis cliquer sur « Comparer / simuler les GPX sélectionnés ». Chaque course utilise son propre départ et ses horodatages source. La durée correspond à l’arrivée moins le départ enregistrés, interruptions entre segments comprises. Les temps aux repères sont interpolés entre les points horodatés à la distance demandée. Aucun modèle, recalage, estimation de pause ni allure saisie n’intervient.

Les GPX doivent contenir coordonnées, altitudes et horodatages ordonnés. Un fichier sans dates ou sans durée positive est refusé avec un message par fichier, sans inventer de temps. L’espacement des repères reste réglable. Les champs de départ imposé, modèle et durée/allure sont masqués dans ce mode. Le tableau identifie explicitement « Temps enregistrés du GPX · sans prédiction ». Les exports portent le suffixe `-enregistre.gpx` et conservent les horaires source aux coordonnées restituées.

Les méthodes de prédiction par modèle, durée ou allure restent sélectionnables pour construire et comparer des scénarios prévisionnels. Les anciennes simulations sont conservées avec leur méthode affichée.

## Version 1.3 : histogramme, carte, import et surveillance

### Histogramme des références

L’écran des références présente quatre groupes de barres correspondant aux profils de dénivelé. Dans chaque groupe, quatre couleurs distinguent les classes de distance : moins de 50 km, de 50 à moins de 100 km, de 100 à moins de 160 km et 160 km ou plus. Chaque barre indique le nombre de références retenues et effectivement analysées ; les fichiers exclus, invalides ou doublonnés n’augmentent pas ces effectifs. Le graphique est actualisé après recalcul et sélection des références.

### Carte de toutes les références

Un quatrième onglet « Carte des références » affiche une carte indépendante du parcours en cours d’analyse. Elle inclut les fichiers natifs et les imports locaux, y compris les courses exclues du modèle. Les traces exclues sont atténuées et en pointillés sur la carte Leaflet. Le filtre « Afficher uniquement les références retenues » permet de les masquer. Le bouton Actualiser recharge les données de la bibliothèque.

Chaque course possède une couleur, une trace respectant les coupures et un marqueur de départ. Cliquer sur la trace ou le marqueur affiche son nom, sa distance et sa sélection. Le tableau donne profil, distance et statut ; « Centrer » cadre une course. Les coordonnées sont allégées pour l’affichage, sans modifier les GPX ni l’apprentissage. Si Leaflet est indisponible, les traces apparaissent sur un dessin SVG sans fond cartographique. Les fichiers non exploitables sont signalés.

### Interrompre un import Garmin

Le bouton « Interrompre l’import Garmin » est actif pendant l’import. L’arrêt est pris en compte entre deux pages de résultats ou deux téléchargements, après la fin de la requête réseau en cours. Un téléchargement dont l’arrêt a été demandé avant son enregistrement n’est pas ajouté. Les activités déjà enregistrées restent dans la bibliothèque. Les modèles sont ensuite actualisés sur ces références et le bilan précise que l’import a été interrompu. L’arrêt ne se déconnecte pas du compte et ne supprime aucune activité distante.

### Surveillance de la validation

La validation et les tests d’inclinaison s’exécutent dans un processus distinct du serveur HTTP. La progression distingue la course en cours, sa courbe et son test d’inclinaison. L’interface affiche le temps depuis la dernière progression et avertit après 30 secondes sans nouvelle étape. Cette alerte indique un calcul long, pas nécessairement une erreur.

Le processus est arrêté si aucune étape n’est publiée pendant 180 secondes ou si la validation dépasse 30 minutes au total. Les calculs incomplets ne sont pas enregistrés comme modèle valide. Un message explique l’arrêt ; le bouton « Relancer la validation » ou l’actualisation des références permet de recommencer. Pour un grand jeu de références, réduire la sélection avant de relancer. Les limites protègent contre une attente indéfinie ; elles ne garantissent pas qu’une validation volumineuse aboutira dans le délai.

La carte et les modes de comparaison enregistrée ou de durée/allure manuelle restent indépendants de la disponibilité du modèle. Les limites de surveillance portent sur la validation et la construction des modèles ; elles ne couvrent pas la lecture initiale des fichiers.

## Migration vers 2.0

La reclassification et le recalcul des modèles se font au redémarrage, avec la surveillance existante. Les imports, sélections, scénarios et GPX sont conservés. Les scénarios déjà enregistrés restent inchangés ; les recalculer en créant de nouveaux runs pour comparer l’ancien et le nouveau résultat. Les règles de segmentation de la section historique « Version 1.3 » sont remplacées par le [modèle 2.0](MODELE-2.0.md).

## Version 2.1

Les fusions, les pas conservés, le filtre visuel de l’histogramme et l’ouverture des détails sont décrits dans [le guide 2.1](MODELE-2.1.md). Les fonctions et descriptions historiques de la version 2.0 restent documentées dans leur contexte. Le classement élargi utilise des retours à la ligne et une présentation mobile adaptée.

## Largeur commune — version 2.1.1

Analyse, Références et modèle, Carte des références et Simulation utilisent désormais la même largeur maximale de 1 800 px, ainsi que leur barre de navigation. Le passage entre les écrans ne change plus la largeur de contenu. Les règles spécifiques à l’impression sont conservées.

## Carte des références en plein écran — version 2.1.2

Le bouton « Carte en plein écran » agrandit la carte et conserve ses commandes de filtre, d’actualisation et de sortie. Le cadrage utilisateur est conservé pendant le redimensionnement. Quitter avec « Quitter le plein écran » ou Échap. Si le navigateur refuse le plein écran natif, un panneau agrandi couvre la fenêtre et reste refermable par les mêmes commandes.

## Critères de profil et distance — version 2.1.3

Les critères d’import et de suppression locale proposent les quatre profils et les cinq classes de distance du modèle, avec un choix « Tous ». Ces critères se combinent avec le type d’activité, les kilomètres et les dates. La liste locale affiche le même ensemble filtré et indique le profil et la classe de chaque course.

Le profil et la classe sont calculés à partir du GPX, puis conservés dans un cache local lié au contenu et aux règles de classification. Les imports existants sont classés à leur prochaine lecture. Une trace illisible reste conservée ; elle ne correspond pas à un profil ou une classe spécifique.

Garmin ne fournit pas ces classifications dans son catalogue : un téléchargement peut être nécessaire avant de décider si la course correspond. Les GPX écartés par ces critères ne sont pas stockés et peuvent être téléchargés à nouveau lors d’un autre import. Les bornes kilométriques utilisent la distance déclarée de l’activité, tandis que la classe utilise la trace GPX. La suppression filtrée utilise tous les critères combinés ; la suppression intégrale conserve sa portée explicite.

## Conversion des imports GPX — version 2.2.0

Le panneau commun « Conversion et optimisation des imports GPX manuels » permet de choisir le traitement avant un import dans Analyse, Références ou Simulation. Le bouton de contrôle/conversion permet aussi de préparer plusieurs GPX sans les ajouter au modèle ni à la comparaison.

- Compacter : retirer la mise en forme XML superflue en conservant les données GPX.
- Alléger pour le simulateur : retirer aussi les extensions, notamment les capteurs (fréquence cardiaque, cadence, température). Les extensions personnalisées sont également retirées.
- Contrôler uniquement : garder les octets du fichier original.

Aucun rééchantillonnage n’est appliqué : les points, pauses stationnaires, segments, coordonnées, altitudes et horaires du GPX sont conservés dans le fichier préparé. Le lecteur d’analyse conserve ensuite son fonctionnement habituel. Les fichiers source sur disque restent intacts. Une sérialisation qui agrandirait le fichier est abandonnée au profit de la source.

Le bilan affiche les tailles avant/après, le gain, le nombre de points et la compatibilité avec les temps enregistrés. Un fichier sans horaires, avec des horaires désordonnés ou sans durée positive ne permet pas ce mode ; utiliser une durée/allure manuelle ou une prédiction si le parcours est exploitable. La conversion ne crée pas d’altitudes ou d’horaires manquants. Un GPX inexploitable affiche une erreur.

Les sources sont limitées à 100 Mio avant conversion ; le résultat doit tenir dans 20 Mio pour être analysé/importé. Un résultat encore trop gros reste téléchargeable mais n’est pas transmis à l’analyse ; essayer le mode allégé. Le compactage seul peut être insuffisant. Le lien télécharge une copie préparée. Les vingt derniers bilans sont conservés dans la page jusqu’à son rechargement ; les données de conversion ne sont pas enregistrées automatiquement dans la bibliothèque locale. Le traitement a lieu dans le serveur local, sans service de conversion externe.

## Navigation et comparaison — version 2.3.0

Les cinq écrans sont Analyse, Références et modèle, Carte des références, Simulation et comparaison, et Conversion GPX. Les actions principales et les quatre profils possèdent des pictogrammes accompagnés de leurs libellés. Le bouton Revenir au départ est supprimé : ramener le curseur de lecture à zéro.

### Présentation au démarrage

Un assistant présente les cinq écrans à la première ouverture et aux ouvertures suivantes tant qu’il n’est pas désactivé. Utiliser Suivant, Précédent, Terminer ou Fermer ; Échap ferme également l’assistant. La case Ne plus afficher au démarrage mémorise le choix dans ce navigateur. Pour réactiver, cliquer sur Découvrir les fonctionnalités dans le ruban puis décocher cette case. Le guide reste consultable même lorsqu’il est désactivé au démarrage. La fermeture restitue l’écran initial.

### Modèle affiché

Dans Vitesse selon la pente, la sélection d’un profil et d’une classe de distance filtre le tableau sur la ligne de ce groupe. Cliquer sur la ligne produit le même résultat. Modèle global et Test inclinaison réaffichent tous les groupes, car ces deux modèles couvrent l’ensemble des références. La sélection du modèle affiché reste indépendante du choix de modèle dans Analyse.

### Conversion GPX

Le traitement des imports se règle dans la page Conversion GPX et s’applique ensuite aussi aux imports manuels des autres pages. Le bouton Contrôler / convertir accepte plusieurs fichiers. Chaque fichier reçoit son bilan et son lien de téléchargement ; les informations et la carte présentent le dernier fichier traité. Les informations du fichier source avant conversion comprennent nom, taille, nombre de points, distance, D+, D−, profil, classe de distance et, si les horaires sont exploitables, durée, départ et arrivée. La carte et le profil coloré décrivent le fichier source, sans prédiction. Un GPX sans horaires peut être visualisé mais ne permet pas une comparaison des temps enregistrés. Le mode allégé et les limites 100 Mio source / 20 Mio résultat restent inchangés.

### Comparaison simultanée

Importer plusieurs GPX puis lancer Comparer / simuler. Par défaut, les temps proviennent des enregistrements GPX, sans modèle. Les méthodes Modèle appris, Durée totale et Allure restent disponibles. Le tableau fournit le nom/fichier, la date de la course (premier horaire GPX lorsqu’il est disponible, sinon départ du scénario), la distance, D+, D−, la durée, le départ, l’arrivée, le profil et la classe de distance. Retirer enlève uniquement le scénario de la comparaison ; le GPX source et la bibliothèque de références restent intacts. L’export GPX de chaque scénario reste disponible.

Chaque scénario dispose d’une carte avec son profil altimétrique à côté ; sur un petit écran, les deux sont empilés. La coloration Pente, Altitude ou Vitesse utilise la même palette bleu-rouge et la même valeur sur la carte et le profil. Les bornes de l’échelle sont indiquées pour chaque parcours. En mode enregistré, la vitesse est observée ; dans les modes prédictifs/manuels, elle correspond à la simulation. Les nouvelles chronologies enregistrées utilisent la grille de relief habituelle pour éviter de colorer les micro-déplacements GPS avec des pentes aberrantes. Les anciens scénarios sont conservés tels quels ; les réimporter pour bénéficier de cette grille.

Lire les traces ensemble démarre une horloge commune en temps écoulé. Chaque départ est aligné à zéro, sans changer la durée des courses ni leurs horaires d’origine dans le tableau. Le champ Départ commun définit uniquement l’affichage des dates/heures de lecture. Le curseur déplace simultanément les positions sur les cartes et les profils ; le multiplicateur règle la vitesse de lecture, comme dans Analyse. Une trace arrivée reste à son arrivée pendant que les autres continuent. Une interruption entre deux segments maintient la position précédente jusqu’au segment suivant. Changer d’écran met la lecture en pause. Pour revenir au départ, ramener le curseur à gauche.

Les scénarios volumineux sont sauvegardés dans IndexedDB dans le même navigateur et à la même adresse locale. Les anciens scénarios de localStorage sont repris et migrés lors de leur prochaine sauvegarde. La limite reste de vingt scénarios. Si le navigateur refuse ou remplit son stockage, un message indique que les scénarios restent disponibles uniquement pour la session courante. Les modèles de référence et les fichiers d’origine ne sont pas modifiés par cette sauvegarde. Sans Leaflet, les cartes disposent d’un tracé SVG de secours sans fond cartographique.

## Carte des références et stratégies — version 2.4.0

### Sélection d’une référence

Le sélecteur de course, une ligne de la liste, le bouton Centrer, la trace ou le point de départ sélectionnent une référence. La carte se centre automatiquement sur les bornes de cette course et une fiche affiche son nom, son profil, sa classe de distance, sa distance, D+, D−, sa durée, ses dates/heures de départ et d’arrivée, ses pauses et sa sélection dans le modèle. La fiche reste accessible en plein écran. Toutes les courses rétablit le cadrage global et masque la fiche. Si le filtre Retenues masque la référence sélectionnée, la sélection est réinitialisée. Sans Leaflet, les tracés SVG sont également sélectionnables à la souris et au clavier.

### Réglages de simulation

Depuis la version 2.4.1, ces réglages se trouvent dans Analyse d’un parcours, dans le bloc Stratégie d’allure du parcours avant Calculer le parcours. Ils s’appliquent au modèle appris, à la durée totale saisie ou à l’allure saisie. Modifier les paramètres puis cliquer sur Calculer le parcours actualise la prédiction, ses horaires, sa carte et son export. Dans Simulation, Ajouter l’analyse actuelle conserve ce résultat et ses réglages dans un nouveau scénario. Les scénarios déjà sauvegardés et les imports directs de GPX dans Simulation restent indépendants de ces réglages. Les temps enregistrés ne sont pas modifiés.

- Évolution de la durée : de −50 à +100 %. −10 % réduit la durée de 10 % ; +10 % l’allonge de 10 %. Il s’agit de pourcentages de temps, pas de vitesse.
- Régulière : conserve la répartition initiale de l’estimation selon le terrain.
- Split positif : première moitié de distance plus rapide, puis ralentissement.
- Split négatif : première moitié plus lente, puis accélération.
- Intensité du split : de 0 à 40 %. Avec 10 %, un split positif répartit la durée initiale en 45 % / 55 % entre les deux moitiés de distance ; un split négatif en 55 % / 45 %. Les différences locales d’allure du modèle restent proportionnelles au sein de chaque moitié. À 0 %, aucune répartition par moitié n’est appliquée.
- Temps en montée : de −50 à +100 %, uniquement sur les portions de pente strictement supérieure à +3 %. Une valeur négative accélère ces montées ; une valeur positive les ralentit. Le plat et la descente ne reçoivent pas ce multiplicateur.

Ordre : répartir d’abord le split en conservant la durée totale initiale, appliquer ensuite le multiplicateur des montées, puis le pourcentage global de durée. Les réglages de montée peuvent donc modifier la répartition finale du split et le gain global. Exemple sans ajustement de montée : 10 h avec split négatif de 10 % et amélioration de durée de 10 % donne 9 h au total, soit 4 h 57 pour la première moitié et 4 h 03 pour la seconde.

Chaque nouveau scénario affiche ses réglages et la variation finale réellement obtenue sous son nom et au-dessus de sa carte. La carte, le profil, les vitesses, les passages, les horaires d’arrivée et l’export GPX utilisent la même chronologie ajustée. Les coordonnées et altitudes restent inchangées ; un point de calcul est ajouté si nécessaire à la moitié de distance. Les pauses estimées conservent leur fraction de la durée totale ; il n’y a pas de nouveau modèle de pauses. Les modèles appris et les fichiers source ne sont pas modifiés. Ces stratégies sont des scénarios paramétrés, pas des gains de performance validés sur les références.

### Thème

La palette utilise le bleu de la mer et du ciel, des gris de roche et des fonds clairs inspirés de assets/thème.jpg. Le bandeau utilise cette image sous un voile sombre pour conserver la lisibilité. Les couleurs de données des parcours restent distinctes de cette palette d’interface.

## Déplacement du bloc de stratégie — version 2.4.1

Le bloc Stratégie d’allure du parcours est placé dans Analyse, avant Calculer le parcours. Un message indique de recalculer après modification des réglages. Le bilan appliqué est affiché dans les résultats. Le transfert vers la comparaison conserve les pourcentages et les temps ajustés. Aucun bloc de réglage n’est désormais présent dans Simulation.

## PrédicTrail — version 3.0.0

Le nom de l’application devient PrédicTrail, par BZHAventure. L’écran Sauvegarde et restauration exporte une archive complète, vérifie un ZIP puis restaure ses données avec une copie de sécurité. Les scénarios et réglages sont désormais synchronisés dans la base locale ; les anciens stockages du navigateur sont repris à la première ouverture. Les nouveaux parcours analysés ou simulés sont conservés localement pour être inclus dans la sauvegarde et permettre la reprise du dernier parcours. Aucun identifiant Garmin n’est sauvegardé. Les détails et limites sont décrits dans [le guide de sauvegarde](SAUVEGARDES.md) et [le guide Windows](DEMARRAGE-WINDOWS.md).
