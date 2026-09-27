# Marassim 3.0.1 — intégration du logo

Le logo fourni est intégré sans modification du fichier PNG : écran de connexion, choix du poste, barre latérale et fenêtre Electron. L’icône Windows adapte uniquement les dimensions au format ICO requis, en conservant les proportions.

Le modèle français remplace ses trois paragraphes de marque par le logo. Le modèle arabe remplace l’image existante. Les textes contractuels, champs de remplissage, tableaux et générateurs métier restent identiques. Les originaux sont conservés dans `branding/original-templates/`.

Au démarrage, le nouveau moteur met à jour les modèles standard précédemment installés dont l’empreinte est connue. Il conserve leur ancienne version dans `data/template-history/before-logo/` et préserve les modèles personnalisés. Les contrats déjà générés ne sont pas réécrits.

## Vérifications

- 22 tests Python et 3 tests Node réussis, dont les trois nouveaux tests de conservation du contenu et de mise à jour des modèles.
- Les exports français et arabe de l’exécutable autonome contiennent exactement le PNG fourni.
- Le rendu Word a été exporté en PDF puis inspecté page par page. La pagination est identique avant et après : une page en français et deux pages en arabe. Le moteur LibreOffice du rendu standard étant indisponible sous cet environnement Windows, le contrôle a utilisé Word en lecture seule.
- L’aperçu des fichiers React compilés affiche le logo correctement. Aucun changement de base réelle n’a été effectué.
- L’installateur 3.0.1 comprend les nouveaux modèles, le manifeste de mise à jour et l’icône Windows. Voir `GUIDE_INSTALLATION.md` pour la mise à jour des cinq PC et le redémarrage du moteur serveur.

Installateur : `release/Marassim-Setup-3.0.1.exe`, 142 035 761 octets. Empreinte SHA-256 : `D523C91638E333006BDEA76CBE9F33AEDE74C5A58C1C06B9C54B5B32F9C49660`. Les modèles et le manifeste livrés ont les mêmes empreintes que leurs fichiers source finaux. La version Windows du programme est `3.0.1.0`.
