# 🎃 Halloween Bot — Discord

Un bot Halloween **jouable**, avec des bonbons, des classements par serveur, une ferme de citrouilles et des événements automatiques. Aucun besoin d'installer des emojis dans le serveur : le bot utilise ses propres décorations Unicode.

## 📜 Les 18 commandes

| Commande | Fonction |
|---|---|
| /halloween | Menu interactif : profil, boutique, classement, guide, ferme |
| /daily | 120 à 260 bonbons toutes les 24 h |
| /trickortreat | Bonbon ou mauvais sort (15 min) |
| /ghosthunt | Capturer des fantômes (5 min) |
| /pumpkin | Ouvrir une citrouille surprise (10 min) |
| /quiz | Questions ou énigmes avec boutons (4 min) |
| /duel | Défier quelqu'un (5 min) |
| /boss | Combat collectif et récompenses (20 min par serveur) |
| /expedition | Explorer une maison hantée (10 min) |
| /farm | Planter, récolter, améliorer son potager hanté |
| /leaderboard | Top bonbons, fantômes, duels, total, récoltes, explorations |
| /profile | Statistiques d'un membre |
| /shop | Boutique interactive, huit objets |
| /inventory | Collection sauvegardée |
| /give | Offrir des bonbons à un membre |
| /achievements | 11 succès à débloquer |
| /guide | Afficher l'aide |
| /setup | Sélectionner le salon d'événements (Gérer le serveur) |

## 🌾 La ferme de citrouilles

Ouvre **/farm** : trois graines sont proposées, avec différentes durées et récompenses. Récolte quand la plantation est prête, puis améliore ton potager jusqu'au niveau 5 (bonus de rendement). Tout est sauvegardé en SQLite, de manière transactionnelle.

## 🔧 Lancer le bot

Python 3.11+ et discord.py 2.x requis.

```sh
pip install -r requirements.txt
python3 main.py
```

**Variable secrète requise sur Railway :** `discord_token` (en minuscules) ou `DISCORD_TOKEN`. Ne jamais publier le token dans GitHub.

**Commande de démarrage :** `python3 main.py`.

Dans Discord, invite le bot avec les scopes `bot` et `applications.commands`, et les permissions **View Channels**, **Send Messages**, **Embed Links** et **Read Message History**. Ensuite, utilise une seule fois **/setup** pour choisir le salon des événements. Les autres jeux fonctionnent sans configuration.

**Stockage durable :** monter un volume Railway sur `/data` et renseigner `DATA_DIR=/data`. Sans volume, Railway peut effacer la base SQLite à chaque redéploiement. Garder **une seule réplique** du bot avec SQLite.

## 🧪 Tests automatiques

```sh
python -m compileall -q main.py halloween_bot tests
python -m unittest discover -s tests -v
```

Le projet comprend des tests de transactions, de classement, de ferme, d'événements, de modules et de registre slash. Les tests ne remplacent pas des essais réels du bot sur un serveur Discord.

## 📂 Structure

- `main.py` : initialisation du bot et chargement des modules.
- `halloween_bot/storage.py` : SQLite, économie, ferme, classements, événements.
- `halloween_bot/economy.py` : bonbons, inventaire, boutique, profil et classement.
- `halloween_bot/games.py` : mini-jeux, duels, boss, expéditions.
- `halloween_bot/farming.py` : panneau interactif de culture et récolte.
- `halloween_bot/events.py` : apparitions, boutons persistants, expiration.
- `halloween_bot/admin.py` : configuration unique du salon.
- `halloween_bot/content.py` : questions, objets, décors.
- `halloween_bot/common.py` : messages, mises en forme, composants communs.

Le jeu utilise uniquement des bonbons virtuels et n'intègre **ni argent réel, ni mises monétaires**.
