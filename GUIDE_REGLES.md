# Module « Règles de réservation »

Les conditions de réservation ne sont plus codées dans `rules.py` : elles se
saisissent dans l'application, onglet **⚖ Règles de réservation** (sidebar).

> **Principe** — pour une réservation donnée, le logiciel cherche la règle qui
> couvre sa **salle** et sa **date**. Tout ce qui sort de cette règle est
> refusé comme conflit. Si aucune règle ne couvre la salle/date, le
> comportement historique s'applique (créneaux 15h-18h / 21h-01h, pause 3h).

## Contenu d'une règle

### 1 · Portée — quand la règle s'applique

| Champ | Rôle |
|---|---|
| **Nom** | Libellé affiché dans les messages de conflit |
| **Salle** | `Almes`, `Chichkhane`, `Rayhane`, ou **Toutes les salles** |
| **Période** | `JJ/MM/AAAA → JJ/MM/AAAA`. Vide = la règle s'applique toujours |
| **Jours** | Cases Lun→Dim. Décoche pour exclure un jour |

### 2 · Conditions horaires

| Champ | Rôle |
|---|---|
| **Créneaux autorisés** | Liste `15:00-18:00`, `21:00-01:00`… Une réservation hors liste est refusée. **Liste vide = horaires libres** |
| **Pause minimale** | Battement obligatoire (heures) entre 2 réservations de la même salle |
| **Heure de fin maximale** | Ex. `21:00` — la réservation ne peut pas finir plus tard |
| **Sono obligatoire** | Refuse la réservation si la sono n'est pas cochée |

Les créneaux qui passent minuit (`21:00-01:00`) sont gérés correctement.

### 3 · Heure de violoniste offerte

Coche **« Cette règle donne droit au violoniste offert »** pour autoriser
l'option sur les réservations couvertes par la règle. Si la case est décochée,
demander le violoniste sur une réservation couverte est **refusé**.

| Champ | Rôle |
|---|---|
| **Début au plus tôt** | Ex. `18:00` |
| **Fin au plus tard** | Ex. `21:00` |
| **Durée max** | En heures (ex. `1`) |
| **Pause entre 2 passages** | Battement dans l'espace Rayhane |

Le moteur vérifie que le créneau de violon ne chevauche **ni** une réservation
principale de Rayhane, **ni** une heure de violon déjà accordée à un autre
contrat. *(Ce second contrôle manquait dans l'ancienne version : deux contrats
pouvaient réserver le même violon au même moment.)*

### 4 · Divers

- **Priorité** — départage deux règles qui couvrent la même situation.

### Comment le logiciel choisit la règle

1. Il garde les règles **actives** dont la salle, la période et le jour de
   semaine couvrent la réservation.
2. Parmi elles, il privilégie celles qui **autorisent le créneau demandé**
   (liste le contenant, ou horaires libres). C'est ce qui permet **une règle
   par créneau** : `Chichkhane 15h-18h → sans violon` et
   `Chichkhane 21h-01h → violon offert` cohabitent sans se gêner.
3. Départage : priorité décroissante → règle à créneaux explicites avant
   règle à horaires libres → salle précise avant « Toutes les salles » → la
   plus récente.
4. Si **aucune** règle n'autorise le créneau, la plus pertinente est retenue
   quand même, pour produire un refus explicite « hors créneau ».
- **Actif** — décoche pour désactiver une règle sans la supprimer.

## Où les règles se voient

- **Nouvelle réservation** — la ligne de disponibilité affiche la règle
  appliquée : `✔ Créneau 15:00-18:00 disponible pour Almes   ⚖ Almes → « Saison haute » 🎻`
- **Calendrier** — les heures de violoniste offertes apparaissent en **violet
  avec 🎻** dans la colonne Rayhane, distinctes des vraies réservations
  Rayhane (vert) et des réservations temporaires (jaune). Le survol affiche le
  contrat d'origine.

## Exemple

| | Règle A | Règle B |
|---|---|---|
| Nom | Saison haute | Rayhane été |
| Salle | Almes | Rayhane |
| Période | 01/06/2027 → 30/09/2027 | *(vide)* |
| Jours | Ven, Sam, Dim | Tous |
| Créneaux | `15:00-18:00` ; `21:00-01:00` | *(vide — libres)* |
| Pause min. | 3 h | 1 h |
| Fin max | — | `21:00` |
| Sono obligatoire | non | oui |
| Violon offert | oui, 18:00→21:00, max 1 h, pause 1 h | non |

## Technique

- Table `reservation_rules` (créée automatiquement au lancement).
- Moteur : `rules.find_matching_rule()` + `rules._validate_with_rule()`.
- Point d'entrée inchangé : `rules.validate_reservation(res, exclude_id, complexe)`.
- UI : `rules_tab.py` (autonome, pas d'import de `gui.py`).
- Les comptes **admin** existants reçoivent automatiquement le nouveau module
  au prochain lancement. Pour un manager/employé : *Gestion des accès*.
