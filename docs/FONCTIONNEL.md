# Fonctionnel, sauvegarde et restauration

PrédicTrail 3.0.0 · documentation consolidée le 8 novembre 2026.

[Architecture, déploiement et démarrage](ARCHITECTURE.md) · [Modèle](MODELE.md)

## Périmètre actuel

L’application estime les temps de passage d’une personne à partir de ses références GPX chronométrées. Six écrans sont disponibles : Analyse d’un parcours, Courses de référence et modèle prédictif, Carte des références, Simulation et comparaison, Conversion GPX, Sauvegarde et restauration. Le ruban affiche le nom PrédicTrail, BZHAventure et les versions. L’assistant de présentation peut être désactivé puis réactivé.

Les sections suivantes décrivent le comportement actuel. Les annexes repliables conservent les détails et évolutions des anciens guides : une fonction décrite sous une ancienne version peut avoir été déplacée ou remplacée depuis.

## Comptes en mode serveur

Une personne peut choisir **Créer un compte** sur la page de connexion. L’administrateur peut aussi créer des comptes depuis **Administration**. Chaque personne utilise son propre espace pour importer des GPX, établir ses références, calculer ses modèles et comparer ses courses. L’espace commence vide. Les analyses manuelles ou enregistrées restent disponibles avant l’import de références chronométrées.

Les réglages, scénarios et sauvegardes sont rattachés au compte. La connexion Garmin facultative est également propre à l’espace de travail. Le bouton **Paramètres du compte** dans le bandeau affiche l’identifiant et le rôle et permet de modifier le mot de passe. **Se déconnecter** met fin à la session. Le bouton **Administration** figure dans la rangée des onglets pour le compte administrateur.

**Administration** affiche les connexions réussies, la dernière connexion en UTC, le temps de connexion estimé et le nombre de traces du dernier modèle calculé. Le suivi commence avec cette version et compte au plus cinq minutes entre deux requêtes. Depuis **Mot de passe oublié**, un utilisateur peut signaler une demande à l’administrateur. Celui-ci peut saisir ou générer un mot de passe provisoire et le transmettre en privé. La réinitialisation d’accès ferme les sessions du compte et impose un nouveau mot de passe à la connexion. Les données sportives et les statistiques du compte sont conservées.

Dans la colonne **Traces dans le modèle**, **Détail par modèle** affiche les effectifs du modèle global, du modèle par inclinaison et des groupes par profil et distance. Pour chaque groupe, il distingue les courses de la classe exacte et celles du même profil utilisées par le modèle de groupe. Si le catalogue retient le repli global, aucune course n’est comptée dans la contribution locale. Les effectifs sont enregistrés après le calcul ou le chargement du modèle.

Dans **Courses de référence et modèle prédictif** et **Carte des références**, l’administrateur peut choisir le compte consulté. Cette vue permet de lire les analyses, les modèles et les traces cartographiques du compte. Le sélecteur **Mon compte** ramène à la bibliothèque de l’administrateur. Les imports, la sélection des références, les exports et les prédictions restent rattachés à son propre espace.

La colonne **Calculs et progression** d’Administration suit l’import Garmin et la mise à jour des références et des modèles par compte. Elle affiche l’étape, le pourcentage, les compteurs disponibles et la durée. Les écrans de consultation affichent le suivi du compte choisi et actualisent la vue à la fin du calcul. Le suivi est actualisé toutes les deux secondes environ et présente les opérations du serveur en cours d’exécution.

## Analyse d’un parcours

Choisir un GPX avec coordonnées et altitudes, puis sélectionner un mode : modèle appris, durée totale, allure au kilomètre ou temps enregistrés. Le dernier mode exige des dates ordonnées et une durée positive ; il reprend les temps du fichier sans prédiction. Les deux modes manuels permettent de calculer sans références initialisées.

Le modèle peut être automatique, global, de groupe relief/distance ou expérimental par inclinaison. Choisir l’espacement des repères de 1 à 50 km. Ajouter des points par kilomètre depuis le départ et un commentaire, par exemple un ravitaillement ; les distances hors parcours sont refusées. La limite est de 200 repères personnalisés et 500 caractères par commentaire. Changer de fichier réinitialise ces repères.

Une date et une heure locales de départ permettent d’afficher les dates et heures de passage et d’arrivée dans le récapitulatif, le tableau, les repères et le suivi de lecture. Après modification, utiliser Recalculer les horaires. Une heure inexistante au changement d’heure est signalée ; les horodatages GPX exportés sont exprimés en UTC.

## Stratégie d’allure

Le bloc se trouve dans **Analyse d’un parcours**, avant Calculer le parcours. Il s’applique à une estimation, jamais aux temps enregistrés, et ne modifie pas les références ni les modèles appris.

- Ajustement global de durée : −50 % à +100 %. Une valeur négative réduit le temps, une valeur positive l’augmente ; il ne s’agit pas d’un pourcentage de vitesse.
- Split positif : première moitié de distance plus rapide, seconde plus lente. Split négatif : première moitié plus lente, seconde plus rapide. Intensité de 0 à 40 % ; le split seul conserve la durée totale initiale.
- Réglage des montées : −50 % à +100 % de durée sur les portions de pente supérieure à +3 %. Le réglage des montées peut modifier le résultat total et l’équilibre final du split.

Le calcul applique le split, le facteur des montées puis l’ajustement global. Exemple : base de 10 h, ajustement de −10 %, split négatif de 10 % et montées à 0 % donnent 9 h, dont 4 h 57 sur la première moitié et 4 h 03 sur la seconde. Ajouter l’analyse actuelle à Simulation conserve cette stratégie.

## Carte, profil et restitution

La carte et le profil partagent la coloration par pente, altitude ou vitesse, ainsi que le suivi de position et les horaires. Le curseur permet de se placer sur le parcours ; lecture/pause et vitesse de 60 à 7 200 fois le temps réel pilotent l’animation. Les commandes restent accessibles en plein écran. Le tableau indique temps cumulés, horaires et sens dominant montée/plat/descente entre repères.

Exporter le parcours GPX conserve sa géométrie et ses segments, ajoute les repères commentés et les horaires estimés lorsqu’un départ est renseigné. Imprimer la prédiction prépare carte, profil, résumé et tableau ; le fond de carte dépend du chargement des tuiles. L’export prépare une trace existante, sans création de nouveaux chemins par dessin. La compatibilité avec chaque appareil GPS reste à vérifier.

## Références et modèle prédictif

Importer des GPX chronométrés ou ajouter des fichiers dans le dossier des références puis actualiser. Les fichiers invalides sont signalés ; les contenus identiques sont dédupliqués. Cocher ou décocher une course change son inclusion dans l’apprentissage et actualise les modèles. L’analyse détaille distance, dénivelés, relief, ascensions, pentes, temps de déplacement, pauses et interruptions.

Le classement s’effectue par famille de relief et classe de distance. La performance est exprimée notamment par l’allure au kilomètre-effort, avec kilomètres-effort = kilomètres + D+/100. La proximité au modèle est calculée en excluant la course elle-même et en utilisant seulement ses pairs de groupe ; sans pair, aucune estimation ni étoile de proximité n’est produite. Les indicateurs du mode automatique global restent distincts.

L’histogramme comporte 20 groupes. Cliquer une barre ou la sélectionner au clavier affiche les courses du groupe et filtre leur classement ; sélectionner à nouveau ou afficher toutes les courses retire le filtre. Cela ne change pas l’inclusion dans le modèle. Le choix du modèle affiché filtre aussi le tableau du catalogue correspondant.

## Carte des références

La carte regroupe les courses natives et importées, y compris celles exclues du modèle selon les filtres. Filtrer par profil, distance et inclusion. Sélectionner une course dans la liste, son tracé ou ses commandes centre automatiquement la carte et affiche nom, profil, classe, distance, D+, D−, durée, horaires, pauses et état d’inclusion. Le bouton plein écran conserve les commandes ; Échap permet d’en sortir.

## Simulation et comparaison

Importer plusieurs GPX chronométrés pour comparer leurs temps réels sans application de prédiction. Les modes prédictifs et manuels restent des choix explicites ; l’ajout de l’analyse actuelle permet aussi de comparer une stratégie. Jusqu’à 20 runs sont conservés comme instantanés : une modification ultérieure des modèles ne les réécrit pas.

Le tableau présente fichier, date, distance, D+, D−, durée, départ, arrivée, profil, classe et retrait. Chaque course a sa carte et son profil coloré. L’horloge de lecture commune aligne visuellement les départs ; les horaires d’origine restent visibles dans le tableau. Le curseur et la vitesse de lecture commandent toutes les positions simultanément. Pendant une coupure d’enregistrement, la position précédente est conservée ; une course terminée reste à l’arrivée. Retirer un run ne supprime pas sa référence.

## Conversion GPX

L’écran dédié affiche les informations du fichier avant conversion, sa carte et son profil. Le mode compact retire le XML superflu tout en conservant les extensions ; le mode allégé pour simulation retire les extensions de capteurs ; le mode original vérifie le fichier. Le traitement conserve points, altitudes, temps, segments et repères : il ne réduit pas le nombre de points et n’invente pas d’horodatages.

Le bilan indique tailles avant/après, réduction et compatibilité d’import. Une source peut atteindre 100 Mio ; le résultat doit rester à 20 Mio ou moins pour être analysé. Un fichier encore trop volumineux peut être téléchargé. Si la conversion agrandit le fichier, l’original est conservé. Pour plusieurs fichiers, l’aperçu concerne le dernier ; les 20 derniers bilans téléchargeables restent liés à la session de page.

## Garmin : importer, arrêter et supprimer

Dans les sources, installer `requirements-garmin.txt` avec Python 3.10 ou supérieur dans l’environnement utilisé pour lancer l’application. Le paquet Windows inclut déjà le connecteur. Saisir le compte, se connecter et répondre à la demande MFA si nécessaire. Mot de passe, code et session restent uniquement en mémoire ; une nouvelle connexion est nécessaire après arrêt du serveur.

Les critères comprennent activité (course, vélo, randonnée ou tous), kilomètres minimum/maximum, dates minimum/maximum, famille de relief et classe de distance. Les bornes renseignées sont inclusives. Les distances déclarées par Garmin servent au filtre kilométrique ; les profils et classes proviennent de l’analyse GPX. Randonnée inclut marche et alpinisme reconnus. Les courses à pied peuvent devenir références ; les autres activités restent exclues sauf sélection explicite.

Les activités inchangées sont ignorées, les révisions mises à jour et le choix d’inclusion conservé. Arrêter l’import agit entre deux requêtes ou enregistrements : l’appel réseau en cours doit se terminer. Les imports déjà enregistrés restent disponibles et alimentent la mise à jour des modèles.

La suppression totale ou filtrée concerne les imports locaux, selon les mêmes critères ; elle ne supprime ni les fichiers natifs de références ni les activités du compte Garmin. Une déconnexion conserve les imports locaux. L’état de connexion et les erreurs distinguent dépendance absente, version incompatible, réseau, délai et réponses HTTP 401/403/429. Une authentification réelle Garmin n’a pas été validée sur ce poste ; les essais utilisent un client simulé et vérifient séparément le chargement des dépendances.

## Sauvegarder

1. Ouvrir l’application dans l’ancien navigateur si des scénarios antérieurs à la version 3.0 doivent être migrés.
2. Aller dans Sauvegarde et restauration, puis Créer une sauvegarde complète.
3. Télécharger le ZIP et en copier une version sur un autre support ou un stockage distant personnel.

L’archive capture un instantané cohérent SQLite et l’état du navigateur courant : imports GPX/Garmin, sélection des références, caches et modèles, scénarios, réglages et repères. Elle inclut les références natives, parcours du projet et sources des nouveaux parcours analysés ou comparés. Les anciens parcours seulement ouverts avant cette version doivent être réimportés pour conserver leur GPX. Les secrets et sessions Garmin sont exclus. Le code de l’application se sauvegarde séparément par le dépôt de sources ou le paquet de diffusion.

Une archive automatique est créée au premier démarrage réussi de chaque journée dans `local/sauvegardes`, sans suppression automatique des anciennes copies. Elle reste sur le même disque : conserver également une copie externe. Les ZIP ne sont pas chiffrés ; choisir un emplacement personnel protégé. Ne pas remplacer ce mécanisme par une copie des fichiers SQLite pendant leur utilisation.

## Restaurer et reprendre

1. Dans l’installation cible, ouvrir Sauvegarde et restauration et sélectionner le ZIP.
2. Vérifier l’aperçu, sa date et sa version, puis cliquer Restaurer les données. Cette action remplace les données courantes.
3. Attendre la fin de restauration et, si nécessaire, la reconstruction des modèles.
4. Vérifier références, scénarios, réglages et repères ; utiliser Reprendre le dernier parcours pour rouvrir sa source conservée.

Avant remplacement, l’application vérifie manifeste, tailles, empreintes SHA-256, chemins autorisés et intégrité SQLite. Elle refuse notamment chemins traversants, liens symboliques, doublons et objets SQLite inattendus. Limites : ZIP 2 Gio, décompression 4 Gio, 10 000 entrées et état utilisateur 40 Mio. Une copie avant-restauration est créée ; une erreur de remplacement déclenche un retour arrière.

Les clés des références sont adaptées au dossier cible. Les modèles peuvent être reconstruits après changement de chemin ou de code ; un échec d’apprentissage ne signifie pas que les données restaurées sont perdues : l’application signale la situation. Éviter toute seconde instance sur les mêmes données. Le paquet Windows utilise un dossier différent des sources ; la sauvegarde/restauration permet le transfert.

## Limites des estimations

Les temps restent des estimations personnelles, dépendantes du nombre, de la diversité et de la qualité des références. Les pauses estimées sont déjà incluses dans la durée apprise ; ne pas les ajouter une seconde fois. La technicité, le sol, la météo, la fatigue et l’altitude physiologique ne sont pas explicitement modélisés. Les réglages de stratégie sont des hypothèses de simulation, pas des gains sportifs démontrés. Voir le guide Modèle pour les règles et les résultats historiques.

## Annexes des documents d’origine

Contenu conservé pour traçabilité. Les indications de version, mesures, limites et emplacements historiques s’interprètent à leur date ; les sections principales ci-dessus font foi pour la version actuelle.

<a id="source-fonctionnel"></a>

<details>
<summary>FONCTIONNEL.md — document source intégral</summary>

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

Les familles sont : Plat / Vallonné, Intermédiaire / Montagne, Dents de scie et Mixte. Les six morphologies initiales restent utilisées pour décrire les parcours et conserver leurs pas d’analyse. Le calcul utilise une grille commune de 25 m, un lissage médian et un seuil d’inversion de 10 m. Il décrit séparément densité de D+, longueur, amplitude et fréquence des ascensions ainsi que leur répartition. Les règles détaillées et les pas d’échantillonnage figurent dans [le guide du modèle 2.0](MODELE.md#source-modele-2-0).

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

Consulter le [guide Garmin](FONCTIONNEL.md#source-garmin) pour les prérequis, les filtres de sélection, la conservation et la suppression locale. Les données importées restent disponibles hors connexion.

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

La reclassification et le recalcul des modèles se font au redémarrage, avec la surveillance existante. Les imports, sélections, scénarios et GPX sont conservés. Les scénarios déjà enregistrés restent inchangés ; les recalculer en créant de nouveaux runs pour comparer l’ancien et le nouveau résultat. Les règles de segmentation de la section historique « Version 1.3 » sont remplacées par le [modèle 2.0](MODELE.md#source-modele-2-0).

## Version 2.1

Les fusions, les pas conservés, le filtre visuel de l’histogramme et l’ouverture des détails sont décrits dans [le guide 2.1](MODELE.md#source-modele-2-1). Les fonctions et descriptions historiques de la version 2.0 restent documentées dans leur contexte. Le classement élargi utilise des retours à la ligne et une présentation mobile adaptée.

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

Le nom de l’application devient PrédicTrail, par BZHAventure. L’écran Sauvegarde et restauration exporte une archive complète, vérifie un ZIP puis restaure ses données avec une copie de sécurité. Les scénarios et réglages sont désormais synchronisés dans la base locale ; les anciens stockages du navigateur sont repris à la première ouverture. Les nouveaux parcours analysés ou simulés sont conservés localement pour être inclus dans la sauvegarde et permettre la reprise du dernier parcours. Aucun identifiant Garmin n’est sauvegardé. Les détails et limites sont décrits dans [le guide de sauvegarde](FONCTIONNEL.md#source-sauvegardes) et [le guide Windows](ARCHITECTURE.md#source-demarrage-windows).

</details>

<a id="source-garmin"></a>

<details>
<summary>GARMIN.md — document source intégral</summary>

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

</details>

<a id="source-sauvegardes"></a>

<details>
<summary>SAUVEGARDES.md — document source intégral</summary>

# Sauvegardes PrédicTrail

L’écran Sauvegarde et restauration crée une archive ZIP complète et permet de la télécharger. Il reprend les scénarios et réglages du navigateur affiché avant de prendre un instantané cohérent de la base SQLite. Les scénarios sont également synchronisés dans la base locale ; les anciennes données IndexedDB/localStorage sont migrées à la première ouverture dans le navigateur concerné.

L’archive contient : base SQLite (imports GPX/Garmin, choix des références, caches de référence et modèles, scénarios et réglages), GPX natifs de référence, parcours du projet et GPX des nouveaux parcours analysés ou comparés. Les anciens parcours uniquement ouverts avant cette version doivent être réimportés pour que leur GPX source soit conservé. Le dernier parcours conservé peut être repris après restauration. Les identifiants, mots de passe, codes MFA et sessions Garmin restent en mémoire et sont exclus.

Une sauvegarde locale automatique est créée au premier démarrage réussi de chaque journée ; elles sont conservées sans suppression automatique. Les copies locales se trouvent à côté de la base dans local/sauvegardes. Elles ne remplacent pas une copie sur disque externe ou sur un stockage distant choisi par l’utilisateur. L’archive n’est pas chiffrée : la conserver dans un emplacement personnel protégé.

## Restauration

Sélectionner le ZIP puis vérifier la date et la version présentées. L’application vérifie la liste des fichiers, les limites de taille, les chemins autorisés et les empreintes SHA-256 avant remplacement. Au clic Restaurer, la base SQLite est contrôlée et une archive avant-restauration est créée. Les fichiers et la base sont remplacés avec retour arrière si un remplacement échoue. Les clés des références sont adaptées au nouveau dossier. Les modèles sont recalculés si nécessaire ; un échec d’apprentissage n’annule pas une restauration de données réussie.

Restaurer remplace les données courantes ; ne pas lancer simultanément deux instances de l’application sur le même dossier de données. Limites : ZIP 2 Gio, contenu décompressé 4 Gio, 10 000 entrées ; état scénarios/réglages 40 Mio. La copie de l’ensemble du dossier sans fermeture du programme ne remplace pas ce mécanisme d’instantané SQLite.

Une sauvegarde manuelle prise depuis un navigateur donné capture ses scénarios ; ouvrir l’application dans l’ancien navigateur avant la première migration pour reprendre ses données. Le dossier de données du paquet Windows est séparé de celui du projet source : transférer les données par sauvegarde/restauration.

</details>
