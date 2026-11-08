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
