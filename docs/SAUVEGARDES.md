# Sauvegardes PrédicTrail

L’écran Sauvegarde et restauration crée une archive ZIP complète et permet de la télécharger. Il reprend les scénarios et réglages du navigateur affiché avant de prendre un instantané cohérent de la base SQLite. Les scénarios sont également synchronisés dans la base locale ; les anciennes données IndexedDB/localStorage sont migrées à la première ouverture dans le navigateur concerné.

L’archive contient : base SQLite (imports GPX/Garmin, choix des références, caches de référence et modèles, scénarios et réglages), GPX natifs de référence, parcours du projet et GPX des nouveaux parcours analysés ou comparés. Les anciens parcours uniquement ouverts avant cette version doivent être réimportés pour que leur GPX source soit conservé. Le dernier parcours conservé peut être repris après restauration. Les identifiants, mots de passe, codes MFA et sessions Garmin restent en mémoire et sont exclus.

Une sauvegarde locale automatique est créée au premier démarrage réussi de chaque journée ; elles sont conservées sans suppression automatique. Les copies locales se trouvent à côté de la base dans local/sauvegardes. Elles ne remplacent pas une copie sur disque externe ou sur un stockage distant choisi par l’utilisateur. L’archive n’est pas chiffrée : la conserver dans un emplacement personnel protégé.

## Restauration

Sélectionner le ZIP puis vérifier la date et la version présentées. L’application vérifie la liste des fichiers, les limites de taille, les chemins autorisés et les empreintes SHA-256 avant remplacement. Au clic Restaurer, la base SQLite est contrôlée et une archive avant-restauration est créée. Les fichiers et la base sont remplacés avec retour arrière si un remplacement échoue. Les clés des références sont adaptées au nouveau dossier. Les modèles sont recalculés si nécessaire ; un échec d’apprentissage n’annule pas une restauration de données réussie.

Restaurer remplace les données courantes ; ne pas lancer simultanément deux instances de l’application sur le même dossier de données. Limites : ZIP 2 Gio, contenu décompressé 4 Gio, 10 000 entrées ; état scénarios/réglages 40 Mio. La copie de l’ensemble du dossier sans fermeture du programme ne remplace pas ce mécanisme d’instantané SQLite.

Une sauvegarde manuelle prise depuis un navigateur donné capture ses scénarios ; ouvrir l’application dans l’ancien navigateur avant la première migration pour reprendre ses données. Le dossier de données du paquet Windows est séparé de celui du projet source : transférer les données par sauvegarde/restauration.
