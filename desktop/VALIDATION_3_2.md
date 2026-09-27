# Validation Marassim 3.2.0

39 tests Python et 5 tests Node réussis. Le serveur Windows compilé a été
testé sur une base isolée : réservation, notification, copie relayée, rapports,
cash-flow J−15, modèles français et arabe, logo et exports Excel.
L'import d'une copie de la base historique ne modifie pas le fichier source.
Les accès concurrents, mises à jour obsolètes et doubles envois sont couverts.

La version React de bureau et la version Vercel ont été construites.
L'interface web a été vérifiée à 390×844, 768×1024 et 1440×940, en mode clair
et sombre. La création d'une réservation fictive sur le serveur de test, suivie
de son transfert, produit une notification dans la cloche en ligne.
Les commandes d'enregistrement du cash-flow restent cachées en lecture seule.

Les tests PostgreSQL utilisent un simulateur du protocole des requêtes ;
ils ne constituent pas une validation d'une base PostgreSQL hébergée.
Le premier transfert réel, les variables privées, la connexion PostgreSQL,
les tâches Windows sur les cinq PC et les notifications push externes restent
à configurer et vérifier sur les installations cibles.

L'installateur `desktop/release/Marassim-Setup-3.2.0.exe` correspond à l'interface,
aux raccordements Electron, au serveur compilé et aux guides présents lors de
sa construction. Empreinte SHA-256 :
`991d720aecb96d8282ae105107479ad62a5f153b67232eeb461808bb4bce995c`.
Les bases, certificats, clés privées, sauvegardes et fichiers de test ne sont
pas distribués. Le manifeste détaillé est dans `release/validation-3.2.0.json`.
