# Marassim 3.2 — consultation en ligne et notifications

Le serveur local garde la base de référence. Les quatre postes travaillent sur
ce serveur par RJ45. Un poste client connecté à Internet transmet une copie
chiffrée vers le site Vercel toutes les 20 minutes. Le serveur n'a pas besoin
d'Internet. Plusieurs relais sont possibles : une copie plus ancienne ne peut
pas écraser une copie plus récente. Une copie incomplète n'est jamais publiée.

## Créer le site

1. Créez votre compte Vercel et importez le dépôt GitHub
   `yassinmejdoub284-cmd/marassim`, branche `main`, dossier racine du dépôt.
   Choisissez une offre autorisant l'usage professionnel ; Hobby est réservé
   aux usages personnels non commerciaux.
2. Connectez une base PostgreSQL hébergée, par exemple Neon depuis le
   Marketplace Vercel. Conservez sa chaîne de connexion dans `DATABASE_URL`.
   La base locale SQLite ne doit jamais être envoyée comme fichier public.
3. Générez les clés sur votre PC avec Python :
   `python desktop/scripts/create-online-secrets.py`.
   Le fichier privé `.env.online.local` est exclu de Git. Ne partagez pas son
   contenu dans le chat. Deux clés aléatoires différentes protègent le transfert
   et les sessions ; les autres valeurs concernent les notifications push.
4. Ajoutez `DATABASE_URL`, `MARASSIM_SYNC_SECRET`, `MARASSIM_SESSION_SECRET`
   aux variables d'environnement Vercel. Pour les notifications quand la PWA
   est fermée, ajoutez aussi `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` et
   `VAPID_SUBJECT` (l'adresse HTTPS réelle du site).
5. Déployez. La configuration fournie construit React et les fonctions Python.
   Jusqu'au premier transfert, la connexion affiche qu'aucune copie n'est reçue.
   Après création du site et de la base, validez une première connexion et les
   rapports : les tests locaux ne remplacent pas cette vérification hébergée.

## Activer un relais

Installez Marassim 3.2.0 sur le serveur puis les quatre postes, après sauvegarde
et arrêt du serveur précédent. Sur un poste client avec Internet, connectez-vous
comme administrateur, ouvrez **Réseau & sauvegardes → Synchronisation en ligne**.
Entrez l'adresse HTTPS du site et la valeur `MARASSIM_SYNC_SECRET`. Configurez
le relais puis synchronisez maintenant. La tâche Windows répète l'envoi toutes
les 20 minutes, même lorsque la fenêtre Marassim est fermée.

Le poste relais doit être allumé, connecté au LAN et à Internet, avec sa session
Windows ouverte. En cas d'interruption, la copie déjà publiée reste consultable ;
le prochain envoi réessaie. La date de la dernière copie apparaît sur le site.
Les sauvegardes quotidiennes à 19h sur les cinq PC restent indépendantes.
Une révocation du relais se fait par l'API administrateur `/cloud/agents/{id}`.

## Utiliser le site

Les identifiants sont ceux de Marassim. Les droits du compte sont conservés :
réservations/calendrier, rapports et cash-flow selon les autorisations locales.
Les modifications de compte se répercutent au prochain transfert. Les sessions
en ligne expirent après une heure. Aucune réservation ni paiement ne peut être
modifié en ligne. Les simulations du cash-flow n'enregistrent pas d'hypothèses.
Les modèles Word français et arabe proviennent du serveur et gardent le logo.

Le bouton de thème propose automatique, clair et sombre et conserve votre choix.
L'interface s'adapte au téléphone, à la tablette et au PC. Sur un navigateur
compatible, choisissez **Installer l'application** ou l'option d'installation
du navigateur. Sur iPhone/iPad : Safari → Partager → Sur l'écran d'accueil.
La PWA nécessite HTTPS. Elle conserve uniquement son interface ; les données
clients et les sessions ne sont jamais placées dans le cache hors connexion.
Une connexion Internet est nécessaire pour ouvrir une nouvelle consultation.

## Notifications de nouvelles réservations

Sur le LAN, la cloche signale les réservations créées après votre première
consultation, avec actualisation toutes les cinq secondes. Cliquez sur
**Activer les notifications** pour les alertes Windows lorsque Marassim est
ouvert et que vous êtes connecté. Un double envoi de la même réservation ne
crée pas deux alertes. Les modifications et les écritures annulées ne créent
pas d'alerte de nouvelle réservation.

En ligne, les alertes arrivent après un transfert réussi, donc jusqu'à 20 minutes
plus tard lorsque le relais fonctionne. La cloche s'actualise toutes les
30 secondes. Les notifications push nécessitent les clés VAPID configurées et
votre accord dans le navigateur. Elles peuvent fonctionner avec la PWA fermée,
selon les réglages du navigateur et du système. Aucun nom, CIN ni montant client
n'est affiché dans une notification système. La déconnexion retire l'abonnement
push de cet appareil. Le premier transfert crée une référence sans alerter pour
toutes les réservations historiques.

## Limites pratiques

Le site utilise PostgreSQL pour conserver des copies chiffrées ; SQLite reste
en mémoire pendant les lectures et aucun fichier SQLite n'est modifié sur
Vercel. Les transferts sont découpés en fragments de 750 ko pour rester sous
les limites des requêtes. Une archive comprimée locale supérieure à 96 Mo est
refusée ; un export de plus de 4 Mo nécessite une période plus courte ou le PC
local. Un serveur restauré sur la même sauvegarde conserve son identité ; un
autre serveur neuf nécessite un nouveau projet ou une réinitialisation explicite
de la base en ligne. Gardez les clés du transfert pour lire les copies chiffrées.
