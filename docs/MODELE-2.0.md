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
