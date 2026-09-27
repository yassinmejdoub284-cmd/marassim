# Validation Marassim 3.0.0 — 27 septembre 2026

L’installateur Windows x64 est disponible dans `release/Marassim-Setup-3.0.0.exe` (141 943 698 octets). Il contient Electron 44.4.5, React et le moteur métier autonome. Il ne contient aucune base réelle ni aucune clé de récupération. Aucun certificat de signature Windows n’a été configuré.

Empreinte SHA-256 de l’installateur :

```text
8312D657A6819B68C0968FEEED5F2EBEB36EC6D0CB8091C03A3AB92E1150BD7D
```

## Résultats

**19 tests Python et 3 tests Electron/Node réussis.**

- Quatre écritures simultanées : une seule réservation pour un créneau occupé, et des numéros distincts pour quatre réservations possibles.
- Réservation de plusieurs salles : annulation complète si une salle est indisponible.
- Modification : application des règles existantes et refus d’une version périmée.
- Acomptes et paiements employés : protection contre les opérations concurrentes et les répétitions après réponse perdue.
- Pointage collectif : mêmes périodes, tarifs et charge groupée Caisse Omar, enregistrés ensemble.
- Droits vérifiés par le serveur, révocation des sessions et validation de l’adresse et du certificat côté Electron.
- Sauvegarde chiffrée, quatre téléchargements HTTPS, contrôle des copies, rattrapage d’un poste absent et restauration avec contrôle d’intégrité.
- Un serveur neuf ou vide ne supprime pas les copies de secours qui subsistent sur les clients.
- Import de la base réelle existante : copie et migration testées, empreinte du fichier source inchangée.
- Documents Word français et arabe : composants XML comparés à ceux des générateurs d’origine. Exports Excel : valeurs et mise en forme comparées.
- Brouillons Word : génération sans créer de réservation.
- Exécutable serveur compilé : démarrage HTTPS, création d’un compte de test, réservation, documents Word/Excel et sauvegarde, sans lancer l’interpréteur Python de développement.

Les deux modèles Word livrés ont exactement les mêmes empreintes que les fichiers originaux. Le serveur et le script de tâches livrés correspondent à leurs versions finales. Les deux scripts PowerShell passent l’analyse syntaxique Windows.

L’interface a été vérifiée dans le navigateur avec une base de test isolée : connexion, formulaire et enregistrement d’une réservation. L’image `release/Apercu-Marassim.png` présente uniquement des données fictives.

## Mise en service restant à faire sur place

Installer le même paquet sur le serveur et les quatre clients, configurer le réseau RJ45, associer les certificats et activer les copies et les tâches Windows selon `GUIDE_INSTALLATION.md`. Vérifier les cinq confirmations, le redémarrage Windows et une restauration sur un poste de secours.

Le serveur et les tâches fonctionnent tant que le compte Windows concerné est connecté. La panne du serveur nécessite une restauration ; les changements depuis la dernière sauvegarde peuvent être perdus. La clé de récupération doit être exportée et conservée séparément, par exemple sur une clé USB. Les cinq PC physiques ne sont pas accessibles depuis cet environnement et n’ont pas été installés ni testés ici.
