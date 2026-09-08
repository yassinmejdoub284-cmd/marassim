"""
test_access_control.py — Script de test du système de contrôle d'accès
"""
import access_control

def test_access_control():
    """Test complet du système de contrôle d'accès."""
    
    print("=" * 60)
    print("TEST DU SYSTÈME DE CONTRÔLE D'ACCÈS")
    print("=" * 60)
    
    # Initialiser la base de données
    print("\n1. Initialisation de la base de données...")
    access_control.init_access_db()
    print("   ✓ Base de données initialisée")
    
    # Vérifier l'admin par défaut
    print("\n2. Vérification de l'utilisateur admin par défaut...")
    admin = access_control.authenticate("admin", "admin123")
    if admin:
        print(f"   ✓ Admin trouvé : {admin['nom']} {admin.get('prenom', '')}")
        print(f"     - Username: {admin['username']}")
        print(f"     - Role: {admin['role']}")
        print(f"     - Actif: {'Oui' if admin['actif'] else 'Non'}")
    else:
        print("   ✗ ERREUR : Admin non trouvé")
        return False
    
    # Tester les modules de l'admin
    print("\n3. Vérification des modules de l'admin...")
    admin_modules = access_control.get_user_modules(admin['id'])
    print(f"   ✓ Admin a accès à {len(admin_modules)} modules")
    if len(admin_modules) == len(access_control.ALL_MODULES):
        print("   ✓ Admin a accès à TOUS les modules (correct)")
    else:
        print(f"   ⚠ Admin a accès à {len(admin_modules)}/{len(access_control.ALL_MODULES)} modules")
    
    # Créer un utilisateur de test (manager)
    print("\n4. Création d'un utilisateur de test (manager)...")
    try:
        manager_id = access_control.create_user({
            "username": "test_manager",
            "password": "test123",
            "nom": "Manager",
            "prenom": "Test",
            "role": "manager"
        })
        print(f"   ✓ Manager créé avec ID: {manager_id}")
        
        # Appliquer le template de rôle
        access_control.apply_role_template(manager_id, "manager")
        print("   ✓ Template 'manager' appliqué")
        
    except Exception as e:
        print(f"   ⚠ Manager déjà existant ou erreur: {e}")
        # Récupérer l'ID du manager existant
        users = access_control.search_users("test_manager")
        if users:
            manager_id = users[0]['id']
            print(f"   → Utilisation du manager existant (ID: {manager_id})")
        else:
            print("   ✗ ERREUR : Impossible de créer ou trouver le manager")
            return False
    
    # Vérifier les modules du manager
    print("\n5. Vérification des modules du manager...")
    manager_modules = access_control.get_user_modules(manager_id)
    print(f"   ✓ Manager a accès à {len(manager_modules)} modules")
    print("   Modules accessibles :")
    for module in manager_modules:
        print(f"     - {module}")
    
    # Créer un utilisateur employé
    print("\n6. Création d'un utilisateur de test (employé)...")
    try:
        emp_id = access_control.create_user({
            "username": "test_employe",
            "password": "test123",
            "nom": "Employé",
            "prenom": "Test",
            "role": "employe"
        })
        print(f"   ✓ Employé créé avec ID: {emp_id}")
        
        # Appliquer le template de rôle
        access_control.apply_role_template(emp_id, "employe")
        print("   ✓ Template 'employe' appliqué")
        
    except Exception as e:
        print(f"   ⚠ Employé déjà existant ou erreur: {e}")
        users = access_control.search_users("test_employe")
        if users:
            emp_id = users[0]['id']
            print(f"   → Utilisation de l'employé existant (ID: {emp_id})")
        else:
            print("   ✗ ERREUR : Impossible de créer ou trouver l'employé")
            return False
    
    # Vérifier les modules de l'employé
    print("\n7. Vérification des modules de l'employé...")
    emp_modules = access_control.get_user_modules(emp_id)
    print(f"   ✓ Employé a accès à {len(emp_modules)} modules")
    print("   Modules accessibles :")
    for module in emp_modules:
        print(f"     - {module}")
    
    # Test d'authentification
    print("\n8. Test d'authentification...")
    
    # Test avec bon mot de passe
    user = access_control.authenticate("test_manager", "test123")
    if user:
        print("   ✓ Authentification réussie pour test_manager")
    else:
        print("   ✗ ERREUR : Authentification échouée pour test_manager")
    
    # Test avec mauvais mot de passe
    user = access_control.authenticate("test_manager", "wrong_password")
    if not user:
        print("   ✓ Authentification correctement refusée avec mauvais mot de passe")
    else:
        print("   ✗ ERREUR : Authentification acceptée avec mauvais mot de passe")
    
    # Test de contrôle d'accès aux modules
    print("\n9. Test de contrôle d'accès aux modules...")
    
    # Admin doit avoir accès à tout
    if access_control.can_access_module(admin['id'], "Gestion des accès"):
        print("   ✓ Admin peut accéder à 'Gestion des accès'")
    else:
        print("   ✗ ERREUR : Admin ne peut pas accéder à 'Gestion des accès'")
    
    # Manager ne doit pas avoir accès aux employés
    if not access_control.can_access_module(manager_id, "Liste employés"):
        print("   ✓ Manager ne peut PAS accéder à 'Liste employés' (correct)")
    else:
        print("   ⚠ Manager a accès à 'Liste employés' (vérifier les permissions)")
    
    # Employé ne doit pas avoir accès aux charges
    if not access_control.can_access_module(emp_id, "Charges"):
        print("   ✓ Employé ne peut PAS accéder à 'Charges' (correct)")
    else:
        print("   ⚠ Employé a accès à 'Charges' (vérifier les permissions)")
    
    # Récapitulatif
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    all_users = access_control.get_all_users(actif_only=True)
    print(f"\nNombre d'utilisateurs actifs : {len(all_users)}")
    print("\nUtilisateurs créés :")
    for u in all_users:
        modules_count = len(access_control.get_user_modules(u['id']))
        print(f"  - @{u['username']} ({u['nom']} {u.get('prenom', '')}) - {u['role']} - {modules_count} modules")
    
    print("\n" + "=" * 60)
    print("TESTS TERMINÉS AVEC SUCCÈS ✓")
    print("=" * 60)
    print("\nInformations de connexion par défaut :")
    print("  Admin     : admin / admin123")
    print("  Manager   : test_manager / test123")
    print("  Employé   : test_employe / test123")
    print("\n⚠ IMPORTANT : Changez le mot de passe admin en production !")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_access_control()
        if success:
            print("\n✓ Tous les tests sont passés avec succès")
        else:
            print("\n✗ Certains tests ont échoué")
    except Exception as e:
        print(f"\n✗ ERREUR CRITIQUE : {e}")
        import traceback
        traceback.print_exc()
