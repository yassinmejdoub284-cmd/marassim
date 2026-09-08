# Guide d'Utilisation - Contrôle d'Accès Marassim

## 🚀 Démarrage rapide

### Première connexion
1. Lancez l'application : `python main.py`
2. Une fenêtre de connexion s'affiche
3. Connectez-vous avec le compte admin par défaut :
   - **Username** : `admin`
   - **Password** : `admin123`
4. ⚠️ **Changez immédiatement le mot de passe admin !**

---

## 👤 Gestion des utilisateurs

### Créer un nouvel utilisateur

1. Connectez-vous en tant qu'**admin**
2. Dans la sidebar, cliquez sur **⚙ Gestion des accès**
3. Dans la fenêtre qui s'ouvre, cliquez sur **Ajouter**
4. Remplissez le formulaire :
   ```
   Nom d'utilisateur : jdupont
   Nom              : Dupont
   Prénom           : Jean
   Rôle             : Manager  (choisir parmi Admin/Manager/Employé)
   Mot de passe     : ******** (minimum 4 caractères)
   Confirmer        : ********
   ```
5. Cliquez sur **Enregistrer**
6. ✅ L'utilisateur est créé avec les permissions par défaut de son rôle

### Modifier un utilisateur existant

1. Dans **Gestion des accès**, sélectionnez l'utilisateur dans la liste
2. Cliquez sur **Modifier**
3. Modifiez les informations souhaitées
4. Pour changer le mot de passe :
   - Saisissez le nouveau mot de passe
   - Confirmez-le
   - Laissez vide si vous ne voulez pas le changer
5. Cliquez sur **Enregistrer**

### Désactiver un utilisateur

1. Sélectionnez l'utilisateur
2. Cliquez sur **Supprimer**
3. Confirmez la désactivation
4. ℹ️ L'utilisateur ne sera plus actif mais ses données restent en base

---

## 🔐 Gestion des permissions

### Personnaliser les accès d'un utilisateur

1. Dans **Gestion des accès**, sélectionnez un utilisateur
2. À droite, la liste des modules s'affiche
3. Cochez/décochez les modules autorisés :
   ```
   ☑ Nouvelle réservation
   ☑ Réservations
   ☑ Calendrier
   ☐ Charges
   ☐ Charges Omar
   ...
   ```
4. Cliquez sur **Enregistrer les modifications**
5. ✅ Les changements sont immédiats

### Appliquer un template de rôle

Si vous voulez réinitialiser les permissions aux valeurs par défaut du rôle :

1. Sélectionnez un utilisateur
2. Cliquez sur **Appliquer template rôle**
3. Confirmez
4. Les permissions standards du rôle sont appliquées

**Templates disponibles :**

- **Admin** : Tous les modules (14 modules)
- **Manager** : Gestion des réservations et finances (9 modules)
- **Employé** : Consultation et acomptes (3 modules)

---

## 📊 Rôles et permissions par défaut

### 🔴 Administrateur (admin)
**Accès complet à tout le système**

✅ Modules accessibles :
- ✓ Nouvelle réservation
- ✓ Réservations
- ✓ Calendrier
- ✓ Ajouter un acompte
- ✓ Charges
- ✓ Charges Omar
- ✓ Journal de Caisse
- ✓ Journal Caisse Omar
- ✓ Modifier réservation
- ✓ Export Excel
- ✓ Ajouter employé
- ✓ Liste employés
- ✓ Pointage
- ✓ Centre de Réception
- ✓ **Gestion des accès** (menu spécial)

### 🟡 Manager (manager)
**Gestion des réservations et opérations courantes**

✅ Modules accessibles :
- ✓ Nouvelle réservation
- ✓ Réservations
- ✓ Calendrier
- ✓ Ajouter un acompte
- ✓ Charges
- ✓ Journal de Caisse
- ✓ Modifier réservation
- ✓ Export Excel
- ✓ Centre de Réception

❌ Pas d'accès à :
- ✗ Charges Omar
- ✗ Journal Caisse Omar
- ✗ Gestion des employés
- ✗ Pointage
- ✗ Gestion des accès

### 🟢 Employé (employe)
**Consultation et ajout d'acomptes uniquement**

✅ Modules accessibles :
- ✓ Réservations
- ✓ Calendrier
- ✓ Ajouter un acompte

❌ Pas d'accès à :
- ✗ Création/modification de réservations
- ✗ Charges et journaux
- ✗ Export
- ✗ Gestion des employés
- ✗ Gestion des accès

---

## 🔄 Utilisation quotidienne

### Se connecter
1. Lancez l'application
2. Entrez votre login et mot de passe
3. Cliquez sur **Se connecter**

### Interface adaptée
- La sidebar affiche **uniquement les modules autorisés**
- Les modules non autorisés sont **masqués automatiquement**
- En haut de la sidebar : votre nom et votre rôle

### Se déconnecter
1. Cliquez sur **🚪 Déconnexion** en bas de la sidebar
2. Confirmez
3. Retour à l'écran de connexion

---

## 🔒 Bonnes pratiques de sécurité

### ✅ À faire
- **Changer le mot de passe admin** dès la première connexion
- Utiliser des **mots de passe forts** (8+ caractères, chiffres, lettres)
- Créer des comptes **individuels** pour chaque utilisateur
- **Limiter** le nombre d'administrateurs (1 ou 2 maximum)
- **Révoquer l'accès** des utilisateurs qui quittent l'entreprise
- **Réviser régulièrement** les permissions accordées

### ❌ À éviter
- Partager le compte admin avec plusieurs personnes
- Utiliser des mots de passe simples (123456, password, etc.)
- Donner des droits admin à tout le monde
- Laisser des comptes inactifs avec des accès

---

## 🆘 Problèmes courants

### "Identifiants incorrects"
- Vérifiez l'orthographe du login et mot de passe
- Les mots de passe sont **sensibles à la casse**
- Par défaut : `admin` / `admin123`

### "Je ne vois pas certains modules"
- Normal ! Vous voyez uniquement les modules autorisés
- Contactez un administrateur pour demander plus de permissions

### "J'ai oublié mon mot de passe"
- Contactez un administrateur
- Il pourra vous attribuer un nouveau mot de passe

### "Je veux plus de permissions"
- Demandez à un administrateur
- Il pourra modifier vos accès dans **Gestion des accès**

---

## 📝 Exemples de scénarios

### Scénario 1 : Nouveau réceptionniste
**Objectif** : Consulter les réservations et encaisser les acomptes

1. Admin crée un compte avec rôle **Employé**
2. Par défaut, il aura accès à :
   - Réservations (consultation)
   - Calendrier (consultation)
   - Ajouter un acompte

### Scénario 2 : Responsable de salle
**Objectif** : Gérer les réservations mais pas les finances complètes

1. Admin crée un compte avec rôle **Manager**
2. Par défaut, accès complet aux réservations
3. Admin peut personnaliser en retirant certains modules :
   - Retirer "Charges" si pas de gestion financière
   - Garder "Ajouter un acompte" et "Journal de Caisse"

### Scénario 3 : Comptable externe
**Objectif** : Voir les finances mais pas modifier les réservations

1. Admin crée un compte avec rôle **Employé**
2. Admin personnalise les accès :
   - Ajouter "Journal de Caisse"
   - Ajouter "Journal Caisse Omar"
   - Ajouter "Charges" et "Charges Omar"
   - Ajouter "Export Excel"
   - Garder "Réservations" en lecture seule

---

## 📞 Support

Pour toute question ou problème :
1. Consultez ce guide
2. Consultez `ACCESS_CONTROL_README.md` pour la documentation technique
3. Contactez votre administrateur système

---

**Version** : 1.0  
**Date** : 2026  
**Application** : Marassim - Système de gestion des réservations
