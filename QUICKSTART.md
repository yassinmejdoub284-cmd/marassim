# 🚀 Quick Start - Système de Contrôle d'Accès

## ⚡ Démarrage en 3 minutes

### 1️⃣ Lancer l'application
```bash
cd c:\Users\yassi\OneDrive\Bureau\marassim_system\marassim_system
python main.py
```

### 2️⃣ Se connecter
- **Username** : `admin`
- **Password** : `admin123`
- Cliquer sur **"Se connecter"**

### 3️⃣ Créer votre premier utilisateur
1. Cliquer sur **"⚙ Gestion des accès"** (dans la sidebar)
2. Cliquer sur **"Ajouter"**
3. Remplir :
   - Login : `manager1`
   - Nom : `Martin`
   - Prénom : `Sophie`
   - Rôle : **Manager**
   - Mot de passe : `manager123`
   - Confirmer : `manager123`
4. Cliquer sur **"Enregistrer"**

✅ **C'est fait !** Vous avez maintenant un système avec contrôle d'accès.

---

## 🎯 Ce que vous pouvez faire maintenant

### En tant qu'Admin
- ✅ Créer/modifier/supprimer des utilisateurs
- ✅ Gérer les permissions de chaque utilisateur
- ✅ Accéder à tous les modules

### En tant que Manager (test : manager1/manager123)
- ✅ Gérer les réservations
- ✅ Voir les finances (charges, journal)
- ❌ Pas d'accès aux employés

### En tant qu'Employé (créez-en un)
- ✅ Consulter les réservations
- ✅ Ajouter des acomptes
- ❌ Pas de modification des réservations

---

## 🔐 Comptes disponibles

| Login | Password | Rôle | Accès |
|-------|----------|------|-------|
| admin | admin123 | Admin | Tous les modules |
| test_manager | test123 | Manager | 9 modules |
| test_employe | test123 | Employé | 3 modules |

💡 Les comptes `test_*` sont créés par le script de test

---

## ⚙️ Tester le système

### Lancer les tests automatiques
```bash
python test_access_control.py
```

Résultat attendu :
```
✓ Base de données initialisée
✓ Admin trouvé
✓ Admin a accès à TOUS les modules
✓ Manager créé avec 9 modules
✓ Employé créé avec 3 modules
✓ Authentification réussie
✓ Tous les tests sont passés avec succès
```

---

## 📚 Documentation complète

| Document | Description |
|----------|-------------|
| `GUIDE_UTILISATION_ACCES.md` | Guide utilisateur complet |
| `ACCESS_CONTROL_README.md` | Documentation technique |
| `IMPLEMENTATION_SUMMARY.md` | Résumé de l'implémentation |

---

## ⚠️ IMPORTANT

### Avant de commencer en production
1. **Changez le mot de passe admin** :
   - Connectez-vous en admin
   - Gestion des accès → Modifier admin
   - Nouveau mot de passe fort

2. **Créez vos vrais utilisateurs** :
   - Supprimez les comptes de test
   - Créez les comptes de votre équipe

3. **Sauvegardez la base** :
   - Copiez `marassim.db` régulièrement

---

## 🆘 Problème ?

### Je ne peux pas me connecter
→ Utilisez `admin` / `admin123`

### Je ne vois pas "Gestion des accès"
→ Normal si vous n'êtes pas admin

### J'ai oublié le mot de passe admin
→ Supprimez `marassim.db` (⚠️ perte de données)

---

## ✅ Checklist première utilisation

- [ ] Lancer l'application
- [ ] Se connecter en admin
- [ ] Changer le mot de passe admin
- [ ] Créer un utilisateur manager
- [ ] Créer un utilisateur employé
- [ ] Tester la connexion avec chaque compte
- [ ] Vérifier que les modules affichés sont corrects
- [ ] Sauvegarder `marassim.db`

---

**Temps estimé : 5 minutes** ⏱️  
**Difficulté : Très facile** 🟢  
**Prérequis : Python installé** 🐍
