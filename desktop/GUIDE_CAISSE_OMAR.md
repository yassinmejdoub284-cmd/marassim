# Caisse Omar — état mensuel automatique

Ouvrir **Journal Caisse Omar**, puis choisir le mois. L'état est généré
automatiquement et actualisé toutes les 30 secondes. Les entrées sont affichées
avant les sorties ; chaque groupe est trié par date.

Le solde de départ est calculé depuis tout l'historique enregistré avant le
premier jour du mois. Le solde de fin = solde de départ + entrées − sorties.
Ce solde devient le solde de départ du mois suivant, même pendant un mois vide
ou au changement d'année. Une correction ancienne recalcule les mois suivants.
Consulter ou exporter l'état ne crée aucune fausse recette de report.

Les recettes sont les montants **Caisse Omar** acceptés au Centre de Réception
et les recettes manuelles Omar. Les acomptes en attente ou refusés sont exclus.
Les dépenses comprennent les charges Omar et les paiements des employés de nuit,
selon les règles déjà utilisées par l'application.

## Dépenses de soirées

Dans Pointage, choisir la date, les périodes, les employés et les réceptions
concernées. Une seule charge est créée pour la session, avec son titre de soirée
(salles et créneaux). Le total et son détail incluent **uniquement les employés
de nuit**. Les employés de jour restent pointés pour leurs fiches, sans charge
dans cette sortie Omar. Les tarifs et montants de la session sont conservés :
modifier plus tard le tarif d'un employé ne réécrit pas ce détail historique.

Les lignes de détail n'ajoutent pas une deuxième dépense. Les anciennes charges
conservent les informations effectivement enregistrées ; des détails par employé
qui n'ont jamais été sauvegardés ne sont pas inventés.

## Imprimer et exporter

**Exporter Excel** et **État PDF à imprimer** produisent un état A4 paysage,
avec Date, Désignation, Débit, Crédit et Solde, solde de départ, totaux et solde
de fin à trois décimales. Les colonnes suivent la présentation fournie :
Débit = entrées et Crédit = sorties. Le logo Marassim reste présent.

Le web propose la même consultation et les mêmes exports après synchronisation.
Il n'autorise aucune création, modification, validation de paiement ou suppression
des données métier. Les droits de chaque compte restent contrôlés côté serveur.
