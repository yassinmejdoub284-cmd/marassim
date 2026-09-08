# `api/` — démonstration web

Ce dossier **n'est pas l'application Marassim**. L'application est un logiciel
de bureau Windows (Tkinter, hors ligne) qui ne peut pas tourner sur un serveur :
elle ouvre des fenêtres, un serveur n'a pas d'écran.

`api/index.py` est une petite page Flask déployée sur Vercel pour la phase de
test : elle permet de montrer le projet depuis n'importe quel appareil, et
surtout d'**essayer le moteur de règles** en ligne.

| Page | Contenu |
|---|---|
| `/` | Calendrier mensuel des 3 salles, heures de violon en violet |
| `/reservations` | Liste des réservations |
| `/regles` | Les règles de réservation et ce qu'elles imposent |
| `/tester` | Formulaire qui appelle `rules.validate_reservation()` |

**Le testeur utilise le vrai moteur** — `rules.py`, le même fichier que
l'application de bureau. Ce qui est refusé ici est refusé dans l'application.

## Données

Fictives, générées par `api/demo_data.py` dans `/tmp` au démarrage. Aucune
donnée client réelle : une URL Vercel est publique.

Sur Vercel, `/tmp` est vidé à chaque redémarrage d'instance : les écritures ne
sont donc pas conservées. C'est voulu — cette page sert à montrer et à tester,
pas à exploiter le complexe.

## En local

```bash
pip install flask
python api/index.py       # http://127.0.0.1:8000
```
