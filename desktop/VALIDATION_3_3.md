# Validation Marassim 3.3.0

45 tests Python et 5 tests Node réussis, dont le test du serveur Windows
compilé sur une base isolée. Les nouveaux cas vérifient le report de décembre
à janvier, un mois vide, une correction ancienne, les recettes Omar acceptées,
l’exclusion des ouvriers de jour et la conservation des tarifs d’une soirée.
Une session regroupant des employés de jour et de nuit ne crée qu’une sortie
Omar pour les employés de nuit, liée aux réceptions sélectionnées.

Les exports Excel et PDF reprennent Date / Désignation / Débit / Crédit / Solde,
avec les entrées avant les sorties. Les détails des employés expliquent le
total de soirée sans ajouter de dépense. Un exemple fictif de trois pages a
été rendu et inspecté : colonnes lisibles, en-têtes répétés, pagination et
solde final présents. Les modèles Word français, contrat arabe, calendrier
Excel et journal Tawfik conservent leurs générateurs et modèles existants.

Les interfaces React locale et web ont été construites. La consultation web
a été contrôlée sur PC, téléphone 390×844 et tablette 768×1024. Le passage au
mois suivant affiche le même solde de départ que le solde de fin précédent.
Les autres modules disposent de listes, consultation et exports autorisés.
Le serveur refuse la création, modification et suppression des réservations,
charges, pointages, validations d’acomptes et utilisateurs en ligne.

Les essais de cloud utilisent un simulateur du protocole PostgreSQL sur des
données fictives. La base PostgreSQL hébergée, les variables privées Vercel et
le premier transfert réel restent à configurer. Les tâches automatiques et
copies sur les cinq PC physiques doivent être vérifiées sur ces postes.
Les bases réelles d’origine et de l’application installée n’ont pas été modifiées.
Les anciennes charges sans détail enregistré par employé restent conservées.

L’installateur `release/Marassim-Setup-3.3.0.exe` contient les interfaces,
raccordements Electron, moteur compilé, logo et guides vérifiés. Les fichiers
distribués ont été comparés aux fichiers construits. Les bases, certificats,
clés privées et fichiers de test ne sont pas distribués.

SHA-256 de l’installateur :
`73d5861f1756c2264025bc08cb6e38208c05695d4907d0a64fc68d84b2f548de`.
Le manifeste détaillé est dans `release/validation-3.3.0.json`.
