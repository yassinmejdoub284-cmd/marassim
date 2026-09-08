# Module de Contrôle d'Accès - Marassim

## Vue d'ensemble

Le système de contrôle d'accès permet de gérer les utilisateurs et leurs permissions d'accès aux différents modules de l'application Marassim.

## Fonctionnalités principales

### 1. Authentification
- **Login sécurisé** : Nom d'utilisateur et mot de passe (hashés avec SHA256)
- **Fenêtre de connexion** : Interface moderne au démarrage de l'application
- **Compte admin par défaut** :
  - Username: `admin`
  - Password: `admin123`
  - Accès à tous les modules

### 2. Gestion des utilisateurs
- **Création d'utilisateurs** : Nom, prénom, login, mot de passe, rôle
- **Modification d'utilisateurs** : Mise à jour des informations et mot de passe
- **Suppression d'utilisateurs** : Désactivation (soft delete)
- **Recherche d'utilisateurs** : Par login, nom ou prénom

### 3. Gestion des rôles
Trois rôles prédéfinis avec permissions différentes :

#### Admin
Accès à tous les modules :
- Nouvelle réservation
- Réservations
- Calendrier
- Ajouter un acompte
- Charges
- Charges Omar
- Journal de Caisse
- Journal Caisse Omar
- Modifier réservation
- Export Excel
- Ajouter employé
- Liste employés
- Pointage
- Centre de Réception
- **+ Gestion des accès** (menu spécial admin)

#### Manager
Accès aux modules de gestion :
- Nouvelle réservation
- Réservations
- Calendrier
- Ajouter un acompte
- Charges
- Journal de Caisse
- Modifier réservation
- Export Excel
- Centre de Réception

#### Employé
Accès limité aux opérations de base :
- Réservations
- Calendrier
- Ajouter un acompte

### 4. Contrôle granulaire des modules
- **Attribution personnalisée** : Chaque utilisateur peut avoir un accès sur-mesure
- **Masquage automatique** : Les modules non autorisés sont cachés de la sidebar
- **Templates de rôle** : Application rapide des permissions standard
- **Modification en temps réel** : Changements visibles immédiatement

## Structure des fichiers

```
marassim_system/
├── access_control.py          # Module principal de gestion des accès
├── login_window.py            # Fenêtre de connexion
├── main.py                    # Point d'entrée (modifié pour login)
├── gui.py                     # Interface principale (modifiée)
└── marassim.db                # Base de données (tables ajoutées)
```

## Tables de base de données

### Table `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nom TEXT NOT NULL,
    prenom TEXT,
    role TEXT NOT NULL,           -- 'admin' | 'manager' | 'employe'
    actif INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### Table `module_access`
```sql
CREATE TABLE module_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    module_name TEXT NOT NULL,
    can_access INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, module_name)
);
```

## Utilisation

### Démarrage de l'application
```bash
python main.py
```

1. La fenêtre de connexion s'affiche
2. Entrez vos identifiants
3. L'application démarre avec les modules autorisés

### Gestion des accès (Admin uniquement)
1. Connectez-vous en tant qu'admin
2. Cliquez sur "⚙ Gestion des accès" dans la sidebar
3. Fenêtre de gestion :
   - **Gauche** : Liste des utilisateurs
   - **Droite** : Modules accessibles pour l'utilisateur sélectionné

#### Ajouter un utilisateur
1. Cliquez sur "Ajouter"
2. Remplissez le formulaire :
   - Nom d'utilisateur (login)
   - Nom et prénom
   - Rôle (Admin/Manager/Employé)
   - Mot de passe (min 4 caractères)
3. Cliquez sur "Enregistrer"
4. Les permissions du rôle sont appliquées automatiquement

#### Modifier un utilisateur
1. Sélectionnez l'utilisateur dans la liste
2. Cliquez sur "Modifier"
3. Modifiez les informations
4. Pour changer le mot de passe : saisissez un nouveau (sinon laissez vide)
5. Cliquez sur "Enregistrer"

#### Gérer les modules
1. Sélectionnez un utilisateur
2. Cochez/décochez les modules autorisés
3. Cliquez sur "Enregistrer les modifications"

#### Appliquer un template de rôle
1. Sélectionnez un utilisateur
2. Cliquez sur "Appliquer template rôle"
3. Confirmer : les permissions standards du rôle seront appliquées

### Déconnexion
- Cliquez sur "🚪 Déconnexion" dans la sidebar
- Confirmez : retour à l'écran de connexion

## Sécurité

### Hachage des mots de passe
- Algorithme : **SHA256**
- Pas de stockage en clair
- Vérification par comparaison de hash

### Contrôles d'accès
- Vérification au niveau de l'interface (masquage des modules)
- Idéalement, ajouter des contrôles côté base de données pour sécuriser davantage

### Recommandations
1. **Changez le mot de passe admin par défaut**
2. Utilisez des mots de passe forts (8+ caractères, mixtes)
3. Limitez le nombre d'admins
4. Révisez régulièrement les permissions

## API Python

### Module `access_control`

#### Gestion des utilisateurs
```python
# Créer un utilisateur
user_id = access_control.create_user({
    "username": "jdupont",
    "password": "motdepasse",
    "nom": "Dupont",
    "prenom": "Jean",
    "role": "manager"
})

# Authentifier
user = access_control.authenticate("jdupont", "motdepasse")
if user:
    print(f"Connecté : {user['nom']}")

# Récupérer tous les utilisateurs
users = access_control.get_all_users()

# Récupérer un utilisateur
user = access_control.get_user(user_id)

# Mettre à jour
access_control.update_user(user_id, {
    "nom": "Martin",
    "password": "nouveaumotdepasse"  # optionnel
})

# Changer le mot de passe
success = access_control.change_password(user_id, "ancien", "nouveau")

# Désactiver
access_control.delete_user(user_id)
```

#### Gestion des modules
```python
# Accorder l'accès à un module
access_control.grant_module_access(user_id, "Nouvelle réservation")

# Révoquer l'accès
access_control.revoke_module_access(user_id, "Charges")

# Récupérer les modules d'un utilisateur
modules = access_control.get_user_modules(user_id)
# → ["Réservations", "Calendrier", ...]

# Récupérer toutes les permissions
perms = access_control.get_all_user_module_permissions(user_id)
# → {"Nouvelle réservation": True, "Charges": False, ...}

# Définir tous les modules en une fois
access_control.set_user_modules(user_id, [
    "Réservations",
    "Calendrier",
    "Ajouter un acompte"
])

# Vérifier l'accès à un module
can_access = access_control.can_access_module(user_id, "Charges")

# Appliquer un template de rôle
access_control.apply_role_template(user_id, "manager")
```

## Personnalisation

### Ajouter un nouveau module
1. Ajoutez le module à la liste dans `access_control.py` :
```python
ALL_MODULES = [
    # ... modules existants
    "Mon Nouveau Module",
]
```

2. Ajoutez-le dans `gui.py` :
```python
NAV_ITEMS = [
    # ... items existants
    ("Mon Nouveau Module", "🆕"),
]
```

3. Créez l'onglet et ajoutez-le dans `_build_tabs()`

### Modifier les templates de rôle
Dans `access_control.py`, modifiez `ROLE_PERMISSIONS` :
```python
ROLE_PERMISSIONS = {
    "admin": ALL_MODULES,
    "manager": [
        "Nouvelle réservation",
        "Réservations",
        # ... ajoutez ou retirez des modules
    ],
    "employe": [
        "Réservations",
        "Calendrier",
    ]
}
```

### Ajouter un nouveau rôle
1. Dans `access_control.py`, ajoutez le rôle à `ROLE_PERMISSIONS`
2. Dans `login_window.py` et `gui.py`, mettez à jour les interfaces

## Dépannage

### Problème : Impossible de se connecter
- Vérifiez que le compte est actif
- Vérifiez l'orthographe du login et mot de passe
- Par défaut : `admin` / `admin123`

### Problème : Modules manquants
- Vérifiez les permissions dans "Gestion des accès"
- Appliquez le template de rôle si nécessaire
- Reconnectez-vous après changement de permissions

### Problème : Erreur au démarrage
- Vérifiez que `marassim.db` existe
- Supprimez `marassim.db` pour réinitialiser (⚠️ perte de données)
- Les tables sont créées automatiquement au premier lancement

## Migration depuis version précédente

L'application détecte automatiquement les tables manquantes et les crée.
**Au premier lancement** :
- Tables `users` et `module_access` créées automatiquement
- Utilisateur admin créé avec tous les accès
- Utilisez `admin` / `admin123` pour la première connexion
- **Changez immédiatement le mot de passe admin !**

## Support et contact

Pour toute question ou problème :
1. Consultez ce README
2. Vérifiez les logs d'erreur
3. Contactez l'administrateur système
