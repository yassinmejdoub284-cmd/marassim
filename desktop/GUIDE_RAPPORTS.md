# Marassim 3.1.0 — Rapports avancés et trésorerie prévue

Les deux modules se trouvent dans le menu **Pilotage**. L’administrateur y accède automatiquement. Pour les autres comptes, cocher **Rapports avancés** et/ou **Cash-flow prévu** dans **Gestion des accès** ; reconnecter ensuite le compte concerné.

## Rapports avancés

Choisir la période et éventuellement une salle, puis cliquer **Actualiser**. Les raccourcis Mois, Trimestre et Année utilisent la période écoulée jusqu’à aujourd’hui. La comparaison couvre la même durée immédiatement précédente.

- Synthèse : forfaits des événements confirmés, acomptes de ces bons, soldes actuels et acomptes datés dans la période.
- Salles et événements : nombre de bons, forfait moyen et répartition.
- Soldes à encaisser : échéance **15 jours avant l’événement**, client, bon, salle et retard.
- Caisses : recettes et sorties des journaux Tawfik et Omar, **toutes salles**.
- Employés : pointage et paiements de la période, tarifs actuels et reste global de la fiche.
- Modes de paiement : acomptes datés par méthode.

Les options temporaires sont exclues des totaux confirmés. Les soldes sont ceux enregistrés actuellement ; ils ne reconstituent pas une clôture historique. Les forfaits suivent la date de l’événement, les acomptes suivent leur date de paiement. Les acomptes sans date restent déduits du solde de leur bon mais sont exclus des encaissements datés avec un message explicatif. Les caisses et les employés ne sont pas filtrés par salle.

**Exporter les rapports** produit un classeur Excel avec neuf feuilles. Les exports Excel habituels et les contrats français et arabes avec le logo restent disponibles dans leurs modules existants.

## Cash-flow prévu

1. Indiquer la date et le **solde initial disponible** à cette date, la fin de prévision et un seuil de sécurité.
2. Choisir le taux de recouvrement supposé des soldes : 100 % projette tout le reste dû, 80 % simule une collecte de 80 %. Ce taux ne modifie aucun contrat et ne réduit pas les mouvements saisis manuellement.
3. Cliquer **Calculer** pour simuler. **Enregistrer les hypothèses** partage la date initiale, le solde, le seuil et le taux sur le serveur. La fin de période, la vue et l’inclusion des soldes échus restent des choix de consultation.
4. Dans **Mouvements planifiés**, ajouter les dépenses futures : loyers, salaires, fournisseurs, énergie, entretien, etc. Il est aussi possible de prévoir une autre entrée.
5. Consulter la vue mensuelle ou hebdomadaire, le minimum quotidien, les alertes et l’échéancier ; exporter la prévision Excel si nécessaire.

Chaque réservation confirmée non soldée apporte une entrée à **J−15** : forfait moins les trois acomptes déjà enregistrés, sans montant négatif. Une réservation soldée ou temporaire n’ajoute rien. Les acomptes déjà versés et les charges enregistrées ne sont pas ajoutés une deuxième fois : le solde initial doit déjà les prendre en compte.

L’option d’inclusion des soldes échus regroupe ces soldes au début de la période. Cette date est une hypothèse de recouvrement ; l’échéance d’origine reste visible dans l’échéancier. Les dépenses futures doivent être planifiées pour obtenir une prévision utile.

Une répétition mensuelle au 31 utilise le dernier jour des mois plus courts puis revient au 31 lorsque possible. Les occurrences antérieures au début de période sont exclues. Modifier ou terminer une répétition concerne **toute la série** ; pour un paiement déjà effectué, reprendre la série à la prochaine échéance afin de conserver les suivantes.

Un mouvement **Réalisé** ou **Annulé** sort de la projection, conserve son historique et peut être remis à l’état Prévu. Ces états ne créent aucun paiement dans les caisses ou les fiches employés : enregistrer les paiements réels dans leurs modules habituels.

Le graphique affiche les soldes de fin de période. Le minimum et les alertes sont calculés **jour par jour**, même si une baisse en cours de mois est suivie d’un rétablissement avant la clôture.

## Utilisation à plusieurs postes et sauvegardes

Les mouvements et hypothèses sont conservés sur le serveur. Chaque écriture est contrôlée pour éviter les doublons et refuser l’écrasement d’une modification effectuée par un autre poste. En cas de conflit, fermer le formulaire et recharger les données avant de modifier à nouveau. Utiliser Calculer/Actualiser pour consulter les dernières écritures.

Les nouvelles données font partie de la sauvegarde chiffrée habituelle et des copies sur les quatre postes. Le fonctionnement quotidien et les conditions réseau sont décrits dans **GUIDE_INSTALLATION.md**.
