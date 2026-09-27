# Marassim — Système de gestion des réservations

## Application Electron + React

La nouvelle application Windows se trouve dans [`desktop/`](desktop/). Elle
conserve le moteur métier historique, les exports Excel et les modèles Word
français et arabe, avec le logo Marassim intégré.

La version 3.2.0 comprend les rapports avancés et le cash-flow prévisionnel.
Le solde d'une réservation est prévu 15 jours avant l'événement, selon le contrat.
Un serveur local centralise les écritures de quatre postes ; les sauvegardes
chiffrées peuvent être répliquées sur les postes clients.

- [Installation sur le serveur et les postes](desktop/GUIDE_INSTALLATION.md)
- [Rapports et cash-flow prévu](desktop/GUIDE_RAPPORTS.md)
- [Validation du logo et des modèles](desktop/VALIDATION_LOGO.md)

Pour développer l'interface, depuis `desktop/` :

```bash
npm ci
npm run dev
```

La version web propose la consultation en lecture seule, les rapports et les
simulations du cash-flow. Elle comprend une PWA installable, les thèmes clair et
sombre et les notifications. Un poste client connecté à Internet envoie une
copie chiffrée du serveur local toutes les 20 minutes.

Sur Vercel, importez **la racine du dépôt (`.`)**, nommée `marassim`, avec le
framework **Vite**. Ne déployez pas `desktop` ni `desktop/server` séparément.
La configuration utilise le `package.json` racine, produit `web-dist/` et sert
les lectures via `api/online.py`. Connectez PostgreSQL et renseignez les variables
privées décrites dans le [guide en ligne](desktop/GUIDE_EN_LIGNE.md).
Les tests locaux utilisent une base PostgreSQL simulée et des données fictives ;
le déploiement hébergé et son premier transfert restent à valider avec votre
compte Vercel et votre base PostgreSQL.

Les données clients, configurations privées, sauvegardes, dépendances et
installateurs générés sont exclus du dépôt. Les données de test sont fictives.

## Application historique

Application de bureau (Python + Tkinter) pour gérer les réservations des
2 salles (**Almes**, **Chichkhane**) et de l'**espace gazon (Rayhane)** du
complexe Marassim : saisie avec vérification automatique des conflits,
génération du **Bon de réservation en Word** à partir du template fourni,
et **export du calendrier en Excel** coloré par salle.

## Installation

```bash
pip install python-docx openpyxl
```

Tkinter est inclus dans Python standard sous Windows/Mac. Sous Linux :
`sudo apt install python3-tk`

## Lancement

```bash
python main.py
```

Une base de données `marassim.db` (SQLite) est créée automatiquement au
premier lancement, dans le même dossier.

## Structure du projet

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée |
| `gui.py` | Interface graphique (3 onglets) |
| `database.py` | Base SQLite (CRUD réservations) |
| `rules.py` | **Toutes** les règles métier / conflits |
| `contract_generator.py` | Remplit `template/Bon_Recu_Marassim_Template.docx` |
| `excel_export.py` | Génère le calendrier Excel coloré |
| `template/` | Le template Word original (ne pas renommer les placeholders `{{...}}`) |

## Nouveautés (v2 — calquée sur ta maquette)

- Le formulaire "Nouvelle réservation" reprend la disposition de ta
  maquette : N° auto en haut à droite, panneau "Réservations existantes
  à la date choisie" (équivalent du tableau Salle/Réservé à/Temp), champs
  Blocage journée, Forfait/Extra, Méthode de paiement, Caisse, Trésorerie,
  Reste d'acompte, Détails Extra, et les 4 cases à cocher (Espace Gazon,
  Tourniquet, Logiciel d'Organisation, Invitations).
- L'espace gazon est maintenant nommé **"Rayhane"** partout (comme sur
  ta maquette) et les couleurs sont : **Almes = bleu, Chichkhane = rouge,
  Rayhane = vert**.
- Nouvel onglet **"Calendrier annuel"** : les 12 mois de l'année avec un
  badge coloré par salle sur chaque jour réservé (initiale + heure), des
  cases à cocher pour filtrer par salle, et des flèches pour changer
  d'année — inspiré de ta 2ᵉ capture d'écran.
  ⚠️ J'ai mis les mois en grille **4 colonnes × 3 lignes** (au lieu de
  6×2) pour que ça reste lisible sur un écran de bureau classique — le
  contenu est identique, juste la disposition. Dis-moi si tu préfères
  une autre disposition.
- Une base `marassim.db` déjà existante est **migrée automatiquement**
  (les nouvelles colonnes sont ajoutées sans perdre tes données).

## Les 3 onglets

1. **Nouvelle réservation** : choisis la salle, la date, le créneau (fixe
   pour Almes/Chichkhane : `15:00-18:00` ou `21:00-01:00` ; libre pour
   Gazon, plafonné à 21h00), les infos client, les acomptes, et
   éventuellement l'option violoniste. Le bouton vérifie toutes les
   règles avant d'enregistrer.
2. **Réservations** : liste toutes les réservations, permet de générer
   le **contrat Word** (dossier `contrats_generes/`) ou de supprimer une
   réservation.
3. **Export Calendrier Excel** : choisis année + mois → génère un fichier
   `.xlsx` avec une colonne par salle, colorée avec la couleur de la
   salle, et une note (commentaire de cellule) avec les détails.

## Règles métier codées (`rules.py`)

- Créneaux fixes Almes/Chichkhane : `15h-18h` et `21h-01h` (3h de pause
  naturelle entre les deux).
- Impossible de réserver deux fois la même salle sur le même jour sans
  au moins **3h de pause**.
- **Option violoniste** (1h gratuite, espace Rayhane) : incluse pour
  tous les contrats **sauf** Chichkhane 15h-18h. Doit se terminer au
  plus tard à **21h00**, nécessite l'espace gazon libre avec **1h de
  pause** avant/après un autre passage.
- **Réception dans l'espace Gazon** (3ᵉ salle) : doit se terminer au
  plus tard à 21h00, nécessite la sono, et **bloque** Almes/Chichkhane
  sur la fenêtre 18h-21h ce jour-là.

### ⚠️ Points à valider avec toi (hypothèses prises)

Ta description contenait quelques zones ambiguës — j'ai fait des choix
raisonnables, **modifiables en 2 minutes** dans `rules.py` :

1. *"si condition de sono... cette option peut choisir n'importe quelle
   date sauf samedi et dimanche"* → j'ai compris : **si l'option
   violoniste est prise avec sono, elle est interdite le samedi et le
   dimanche**. Si le sens est différent, ajuste
   `JOURS_INTERDITS_VIOLONISTE_AVEC_SONO` dans `rules.py`.
2. Les couleurs par salle (`SALLE_COLORS` dans `rules.py`) sont des
   couleurs par défaut — change les codes hexadécimaux si tu veux
   d'autres couleurs précises.
3. Le numéro de bon est généré automatiquement (`BON-ANNÉE-ID`) — dis-moi
   si tu veux un format différent (ex: `FAC-2026-0008`).

## Prochaines étapes possibles

- Export PDF direct du contrat (déjà possible via LibreOffice en ligne
  de commande si besoin).
- Vue calendrier visuelle dans l'app elle-même (actuellement uniquement
  via l'export Excel).
- Gestion multi-utilisateurs / sauvegarde cloud de `marassim.db`.
