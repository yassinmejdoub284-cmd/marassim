# Marassim en multi-poste (PostgreSQL)

L'application fonctionne dans deux modes, choisis par le fichier `marassim.ini` :

| Mode | Quand | Configuration |
|---|---|---|
| **SQLite** (défaut) | Un seul poste | Pas de `marassim.ini` — comportement d'origine |
| **PostgreSQL** | Plusieurs postes partageant les mêmes données | `marassim.ini` sur chaque poste |

> **Pourquoi pas un simple dossier partagé ?** SQLite pose ses verrous avec des
> mécanismes que les partages réseau Windows n'honorent pas de façon fiable. À
> 4 postes en saisie simultanée, le risque n'est pas la lenteur : c'est la base
> corrompue. PostgreSQL est conçu pour ça.

---

## A · Sur le PC serveur (celui qui reste allumé)

### 1. Installer PostgreSQL

Télécharge l'installeur Windows sur **postgresql.org/download/windows**.
Pendant l'installation : note le mot de passe du superutilisateur `postgres`,
garde le port **5432**, et tu peux décocher « Stack Builder » à la fin.

### 2. Créer la base et l'utilisateur

Ouvre **SQL Shell (psql)** depuis le menu Démarrer, valide les valeurs par
défaut, saisis le mot de passe `postgres`, puis :

```sql
CREATE USER marassim WITH PASSWORD 'un_mot_de_passe_solide';
CREATE DATABASE marassim OWNER marassim;
\q
```

### 3. Autoriser les autres postes

Deux fichiers à éditer dans `C:\Program Files\PostgreSQL\16\data\`
(ouvre le Bloc-notes **en tant qu'administrateur**) :

**`postgresql.conf`** — cherche `listen_addresses` et mets :

```
listen_addresses = '*'
```

**`pg_hba.conf`** — ajoute à la fin, en adaptant à ton réseau local :

```
host    marassim    marassim    192.168.1.0/24    scram-sha-256
```

Puis redémarre le service : touche Windows → `services.msc` →
**postgresql-x64-16** → clic droit → Redémarrer.

### 4. Ouvrir le pare-feu

PowerShell **en administrateur** :

```powershell
New-NetFirewallRule -DisplayName "PostgreSQL Marassim" -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Allow
```

### 5. Noter l'adresse IP du serveur

```powershell
ipconfig
```

Relève l'**Adresse IPv4** (ex. `192.168.1.10`). Fixe-la dans ton routeur (bail
DHCP statique) — si elle change, tous les postes perdent la connexion.

---

## B · Migrer les données existantes

**Une seule fois**, depuis le poste qui détient `marassim.db` :

1. Copie `marassim.ini.example` en `marassim.ini` et renseigne l'IP du serveur
   et le mot de passe choisi à l'étape A.2.
2. Installe le pilote : `pip install psycopg2-binary`
3. Lance :

```
python migrate_to_postgres.py
```

Le script crée le schéma, copie chaque table, recale les compteurs d'ID et
compare les totaux. **Il ne modifie jamais `marassim.db`** — garde ce fichier
comme sauvegarde de l'avant-migration.

S'il refuse en disant que la base contient déjà des données, c'est une
sécurité : vide la base PostgreSQL, ou relance avec `--force`.

---

## C · Sur chaque poste client

1. Copier le dossier de l'application (sans `marassim.db`).
2. `pip install -r requirements.txt`
3. Copier `marassim.ini.example` en `marassim.ini`, avec l'IP du serveur et le
   mot de passe. **Le même fichier sur tous les postes.**
4. Lancer `python main.py`.

Si le serveur est injoignable, l'application affiche un message expliquant quoi
vérifier, au lieu de planter.

---

## D · Sauvegardes

C'est le point le plus important du multi-poste : les données ne sont plus sur
le poste de chacun, elles sont **uniquement** sur le serveur.

Sur le PC serveur, crée `C:\marassim_backup\sauvegarde.bat` :

```bat
@echo off
set PGPASSWORD=un_mot_de_passe_solide
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set D=%%c-%%b-%%a
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U marassim -h localhost marassim > "C:\marassim_backup\marassim_%D%.sql"
forfiles /p "C:\marassim_backup" /m *.sql /d -30 /c "cmd /c del @path"
```

Puis planifie-le : Démarrer → **Planificateur de tâches** → Créer une tâche de
base → tous les jours à 23 h → Démarrer un programme → ce `.bat`.

Copie régulièrement le dossier `C:\marassim_backup` ailleurs (clé USB, OneDrive,
disque externe). Une sauvegarde qui vit sur la machine qu'elle protège n'en est
pas une.

**Pour restaurer :**

```
psql -U marassim -h localhost -d marassim < C:\marassim_backup\marassim_2026-09-08.sql
```

---

## E · Revenir en mono-poste

Renomme ou supprime `marassim.ini`. L'application repasse sur `marassim.db` en
local, sans autre changement.

---

## F · En cas de problème

| Symptôme | Cause probable |
|---|---|
| « base de données inaccessible » au lancement | PC serveur éteint, ou IP changée dans `marassim.ini` |
| `password authentication failed` | Mot de passe erroné dans `marassim.ini` |
| `no pg_hba.conf entry for host` | La plage IP de l'étape A.3 ne couvre pas ce poste |
| `timeout expired` | Pare-feu du serveur (étape A.4) |
| `No module named psycopg2` | `pip install psycopg2-binary` sur ce poste |

Pour tester la connexion sans lancer l'interface :

```
python -c "import db; print(db.ping())"
```

---

## Notes techniques

- `config.py` lit `marassim.ini` ; `db.py` traduit le SQL entre les deux moteurs.
  Le reste du code écrit du SQL « style SQLite » et n'a pas à savoir où il tourne.
- L'attribution du numéro de bon se fait désormais dans **une seule
  transaction** avec l'insertion (`insert_reservation_with_bon`). Auparavant
  l'INSERT et l'UPDATE passaient par deux connexions distinctes : deux postes
  simultanés pouvaient obtenir le même numéro.
- PostgreSQL fait respecter les clés étrangères, ce que SQLite ignorait par
  défaut. Un pointage qui référence un employé supprimé sera désormais refusé.
- `marassim.ini` contient un mot de passe et n'est pas versionné dans Git.
