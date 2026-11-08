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
