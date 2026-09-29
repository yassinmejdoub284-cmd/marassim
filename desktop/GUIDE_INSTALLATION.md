# Marassim — Electron + React, 1 serveur et 4 postes

La nouvelle interface conserve les modules de l’application Python et réutilise son moteur métier. Les deux fichiers Word de `template/` conservent leurs textes, champs et tableaux ; leur en-tête utilise le logo Marassim fourni. Le calendrier Excel et le journal Tawfik gardent les modèles d’origine. L’état Omar adopte la présentation papier demandée, avec report mensuel automatique. La base d’origine n’est pas modifiée.

## Installation Windows

Après sa compilation et sa validation, installer `Marassim-Setup-3.4.0.exe` sur les cinq PC Windows 64 bits. L’installateur contiendra Electron, React et le moteur métier : Python et Node.js ne seront pas nécessaires sur ces PC. Le code Web publié sur GitHub ne constitue pas cet installateur.

### Nouveautés 3.4.0

Le formulaire de réservation vérifie la date, les salles et les heures ; le serveur revérifie au moment d’enregistrer pour éviter les conflits entre postes. Les horaires sont libres par défaut, avec une pause de 3 heures entre deux locations de la même salle, configurable à 2 heures dans les règles. L’heure gratuite de violoniste à Rayhane suit les exceptions Chichkhane 15 h–18 h et samedi/dimanche. La cloche signale les réservations, les paiements et les retards ; le nouveau module **Paiements en retard** est consultable aussi sur le Web. Voir `GUIDE_RESERVATIONS.md`.

### Nouveautés 3.3.0

Caisse Omar mensuelle générée automatiquement, report du solde depuis tout l’historique, état Excel et PDF au format Date / Désignation / Débit / Crédit / Solde. Les sorties de soirées conservent le détail des employés de nuit uniquement. Voir `GUIDE_CAISSE_OMAR.md`. Le web permet aussi de consulter et exporter les autres modules selon les autorisations ; il reste sans écriture métier.

Thème clair, sombre ou automatique ; cloche et notifications de nouvelles réservations ; relais vers la consultation Vercel toutes les 20 minutes depuis un poste client avec Internet. Le site React propose une PWA et une interface adaptée au téléphone, à la tablette et au PC. Consulter `GUIDE_EN_LIGNE.md` pour créer le site, connecter PostgreSQL et activer le relais. Aucune modification de réservation ou de paiement n’est autorisée en ligne.

### Nouveaux modules de pilotage en 3.1.0

Le menu **Pilotage** propose **Rapports avancés** et **Cash-flow prévu**, avec exports Excel. Le solde des réservations confirmées est prévu **15 jours avant l’événement**, déduction faite des acomptes enregistrés. Les dépenses futures se renseignent dans Mouvements planifiés. Consulter `GUIDE_RAPPORTS.md` pour les hypothèses, filtres et échéances.

Pour mettre à jour depuis 3.0.1 à 3.3.0, créer une sauvegarde, fermer Marassim sur les cinq postes, arrêter la tâche `Marassim-Serveur` et le processus `MarassimServer.exe` sur le serveur, puis installer 3.4.0 et relancer Marassim. Installer la même version sur les quatre clients. Les nouvelles colonnes de notifications sont ajoutées à la base utilisée par le serveur ; les réservations, paiements et documents existants restent conservés. Donner les permissions nécessaires aux comptes concernés dans Gestion des accès.

### Mise à jour du logo depuis la version 3.0.0

Fermer les fenêtres Marassim sur les cinq postes. Sur le serveur, arrêter la tâche `Marassim-Serveur` et le processus `MarassimServer.exe` avant la mise à jour, puis relancer Marassim après installation. Les modèles standard déjà copiés sur le serveur sont mis à jour au démarrage du nouveau moteur ; leurs versions précédentes sont conservées dans `data/template-history/before-logo/`. Les modèles personnalisés sont préservés. Les originaux du projet sont également conservés dans `desktop/branding/original-templates/`. Les documents déjà générés ne sont pas modifiés. Installer la même version sur les quatre clients.

### PC serveur

1. Brancher les cinq PC sur un **switch réseau**, avec cinq câbles RJ45. Donner au serveur une adresse IP fixe ou une réservation DHCP, par exemple `192.168.1.10`.
2. Au premier lancement, cliquer **Reprendre ma base Marassim existante**, puis sélectionner la base `marassim.db`. L’application crée une copie et migre uniquement cette copie. Les comptes, acomptes, employés, caisses et règles existants sont repris. Ne pas utiliser simultanément l’ancienne application après la bascule : elle continuerait à écrire dans l’ancienne base.
3. Si l’on commence sans données existantes, cliquer **PC serveur**, puis créer un compte administrateur. Il n’existe aucun mot de passe par défaut dans une installation neuve. Avec une base importée, utiliser les comptes existants.
4. Dans le pare-feu Windows, autoriser le port **TCP 7443**, uniquement pour le réseau **Privé** et le sous-réseau local. Une personne disposant des droits administrateur Windows peut exécuter :

   ```powershell
   New-NetFirewallRule -DisplayName 'Marassim LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7443 -Profile Private -RemoteAddress LocalSubnet
   ```

5. Ouvrir **Réseau & sauvegardes**, exporter la **clé de récupération** sur une clé USB conservée séparément du serveur, puis cliquer **Installer les tâches automatiques**.
6. Le serveur démarre à la connexion du compte Windows qui a installé la tâche et continue à fonctionner quand la fenêtre Marassim est fermée. Ce compte doit rester connecté. Désactiver la mise en veille du serveur pendant les heures de travail. Le démarrage avant connexion Windows nécessite une installation comme service Windows par l’administrateur informatique ; ce paquet utilise une tâche à l’ouverture de session.

### Chacun des quatre PC clients

1. Entrer `https://192.168.1.10:7443` et cliquer **Vérifier la connexion**.
2. Comparer l’empreinte affichée avec celle de **Réseau & sauvegardes** sur le PC serveur. Cliquer **L’empreinte correspond · Associer ce poste**. Les connexions suivantes exigent ce certificat, même si un autre ordinateur reprend cette adresse IP.
3. Se connecter comme administrateur le temps de la configuration. Dans **Réseau & sauvegardes**, choisir un nom unique, par exemple `Accueil 1`, `Accueil 2`, `Direction`, `Caisse`, et cliquer **Activer les copies**.
4. Cliquer **Installer les tâches automatiques**. La tâche contrôle les sauvegardes toutes les cinq minutes tant que le compte Windows est connecté, y compris quand Marassim est fermé. Si Windows bloque l’enregistrement de la tâche, exécuter le script fourni avec les droits adaptés à la politique de ce PC.
5. Se déconnecter de Marassim et utiliser le compte de travail habituel. Les sauvegardes utilisent l’autorisation du poste et continuent indépendamment du compte Marassim connecté.

## Fonctionnement à plusieurs postes

- Une seule base active, sur le disque local du serveur. Les postes ne partagent jamais un fichier SQLite sur le réseau.
- Chaque écriture prend une transaction `BEGIN IMMEDIATE` ; vérification des disponibilités, règles, numéros de bon et enregistrement sont validés ensemble. Une réservation de plusieurs salles est entièrement enregistrée ou entièrement annulée.
- Les mises à jour portent une version. Une opération fondée sur une ancienne version est refusée avec un message demandant de recharger le dossier. Les acomptes utilisent la même protection.
- Une clé de transaction évite de compter deux fois une opération répétée après une coupure réseau. Aucun paiement n’est enregistré localement en attente de connexion.
- Les listes s’actualisent périodiquement ; un formulaire déjà ouvert reste protégé par sa version.
- Le pointage collectif conserve les périodes et les tarifs existants, ainsi que la charge groupée des ouvriers de nuit dans la Caisse Omar. Le pointage et cette charge sont maintenant atomiques.

## Sauvegardes quotidiennes

Une sauvegarde est créée au premier démarrage, après une journée manquée et chaque jour à **19:00, heure Windows du serveur**. La base est copiée avec l’API SQLite de sauvegarde, puis contrôlée avec `integrity_check`. L’archive contient la base entière, les comptes et autorisations, les modèles Word et les informations de contrôle. Elle est chiffrée. La clé de déchiffrement n’est pas stockée dans l’archive.

Les quatre postes téléchargent les archives, vérifient leur taille et leur empreinte SHA-256, écrivent un fichier temporaire puis le remplacent atomiquement. Ils confirment au serveur la copie vérifiée. Le compteur **5/5** signifie : une copie sur le serveur et quatre confirmations de la dernière archive. Ce compteur rapporte la dernière confirmation, pas une vérification continue de l’état physique des disques.

Un poste éteint ne peut pas recevoir une sauvegarde. Il rattrape automatiquement toutes les archives encore disponibles dès sa prochaine connexion. Les copies ne sont complètes sur les cinq PC qu’après leur synchronisation. Les archives sont gardées pendant **30 jours de sauvegarde distincts** ; plusieurs sauvegardes manuelles ne raccourcissent pas cette durée.

La panne du serveur empêche les nouvelles saisies jusqu’à restauration. Ce système fournit des copies de secours, pas un basculement automatique. Une sauvegarde quotidienne ne peut pas protéger les changements effectués depuis la dernière copie ; utiliser **Sauvegarder maintenant** puis vérifier les cinq confirmations avant une maintenance.

### Emplacement des fichiers

Dans le dossier de données de l’application Electron : `%APPDATA%\Marassim\`.

- Serveur : `data\marassim.db`, `data\backups\`, `data\recovery.key`, `data\server.log`, `data\template\`.
- Client : `backups\`, `replica.json`, `connection.json`.
- Les tâches automatiques restreignent l’accès au dossier au compte Windows courant, à SYSTEM et aux administrateurs.
- Les documents Word et Excel sont enregistrés à l’endroit choisi dans la boîte de dialogue, puis ouverts avec l’application Windows associée.

## Restaurer après une panne SSD

1. Choisir le fichier `.mrb` le plus récent parmi les quatre PC et récupérer la clé USB contenant `Marassim-recovery.key`.
2. Sur le nouveau serveur, installer Marassim. Fermer sa fenêtre et arrêter la tâche `Marassim-Serveur` et le processus `MarassimServer.exe` s’ils fonctionnent déjà.
3. Dans PowerShell, appeler l’exécutable du moteur livré avec l’application (sous `resources\server\MarassimServer.exe`) :

   ```powershell
   & 'C:\chemin\Marassim\resources\server\MarassimServer.exe' --restore 'D:\copie\marassim_....mrb' --key 'E:\Marassim-recovery.key' --destination 'C:\Marassim-Restauration'
   ```

   Le dossier de destination doit être vide. La commande vérifie l’archive et la base, puis restaure les modèles. Elle refuse d’écraser un dossier existant contenant des fichiers.
4. Garder une copie de l’ancien dossier `data`. Placer les fichiers restaurés dans le dossier `data` du nouveau poste, avant de relancer le serveur. Les anciens certificats ne sont pas restaurés ; un nouveau certificat est créé.
5. Ouvrir Marassim en mode serveur et vérifier les dossiers et les caisses. Réassocier les quatre clients avec la nouvelle empreinte, puis enregistrer à nouveau leurs autorisations de copie. Les sessions et les anciennes autorisations des postes sont invalidées lors de la restauration.
6. Créer une sauvegarde, synchroniser les quatre clients et vérifier **5/5**. Conserver les archives précédentes jusqu’à validation de la restauration.

Sans la clé de récupération exportée, les archives chiffrées ne peuvent pas être restaurées.

## Développement et compilation

Pré-requis de compilation : Windows x64, Node.js 22 ou plus récent, Python 3.11+.

```powershell
npm install
python -m pip install -r server/requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
npm test
./scripts/build-server.ps1
npm run package
```

L’installateur est créé dans `release/`. La base réelle, les mots de passe et la clé de récupération ne sont jamais inclus dans l’installateur.

Développement : lancer `npm run dev`, puis dans un autre terminal définir `MARASSIM_DEV_URL=1`, éventuellement `MARASSIM_PYTHON`, et lancer `npm start`. L’application compilée charge uniquement ses fichiers React locaux et fonctionne sans connexion Internet.

`http://127.0.0.1:5173/?preview=1` fournit un aperçu visuel clairement marqué avec des données fictives, en lecture seule. Ce mode ne sert jamais de repli à une connexion serveur en panne.

## Validation sur le réseau réel

Les tests automatisés couvrent les écritures concurrentes, les reprises d’opérations, les sauvegardes chiffrées, quatre copies réseau HTTPS et une restauration. Avant la mise en service, tester les mêmes opérations sur les cinq PC, débrancher un client pour vérifier le rattrapage, redémarrer Windows pour vérifier les tâches, et restaurer une archive sur un poste de secours. Les cinq machines ne sont pas accessibles depuis cet espace de développement ; leur installation et cette validation restent à effectuer sur place.

Références techniques : [sécurité Electron](https://www.electronjs.org/docs/latest/tutorial/security), [transactions SQLite](https://www.sqlite.org/lang_transaction.html), [sauvegarde SQLite](https://www.sqlite.org/backup.html).
