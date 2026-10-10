# 🎃 Halloween Bot — Discord

Un bot Halloween **jouable**, avec des bonbons, des classements par serveur, une ferme de citrouilles et des événements automatiques. Aucun besoin d'installer des emojis dans le serveur : le bot utilise ses propres décorations Unicode.

## 📜 Commandes classiques

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
| /leaderboard | Compétition par défaut, bonbons, fantômes, duels, total, récoltes, explorations |
| /profile | Statistiques d'un membre |
| /shop | Boutique interactive, huit objets |
| /inventory | Collection sauvegardée |
| /give | Offrir des bonbons à un membre |
| /achievements | 11 succès à débloquer |
| /guide | Afficher l'aide |
| /setup | Sélectionner le salon d'événements (Gérer le serveur) |

## 🎨 Décoration et emojis du bot

Le bot affiche des panneaux Discord avec titres, sections, couleurs et boutons uniformes.
Il peut utiliser **ses propres emojis d'application**, même dans un serveur qui ne possède aucun emoji Halloween.

Dans le **Discord Developer Portal**, ouvre ton application > **Emojis** et ajoute des images pour créer par exemple :

- pumpkin / halloween_pumpkin
- candy / halloween_candy
- ghost / halloween_ghost
- bat / halloween_bat
- skull / halloween_skull
- trophy, shop, bag, garden, web, spider, lantern

Le bot les récupère automatiquement au démarrage et les affiche dans ses embeds, ses boutons et ses menus.
S'il ne trouve pas un emoji, il affiche un emoji Unicode correspondant sans erreur. Aucun réglage n'est nécessaire dans /setup.

Le chargement des emojis de l'application nécessite discord.py 2.5 ou plus récent.
Après avoir ajouté des emojis, redémarre simplement le service Railway.
## 🏆 Halloween Cup — compétition de saison

Le bot conserve **deux classements distincts** :

1. **Halloween Cup / compétition** : points attribués uniquement à des
   **défis de réflexion correctement résolus**, avec trois tentatives différentes
   par jour. Aucun achat, don de bonbons, événement aléatoire, boss ou duel
   de chance ne modifie ces points.
2. **Économie Halloween classique** : bonbons, fantômes, récoltes, objets,
   duels et autres statistiques pour jouer sans enjeu.

### Commandes

| Commande | Fonction |
|---|---|
| /competition | Arène interactive (inscription, défis, Top 10, rang, règlement) |
| /challenge | Trois défis individuels, différents chaque jour |
| /competition_top | Classement officiel par points de saison |
| /competition_rank | Rang, division Bronze → Légende, progression |
| /leaderboard | Affiche les scores de compétition par défaut ; autres catégories possibles |
| /tournament_start | Lancer une saison, réservé aux membres ayant Gérer le serveur |
| /tournament_close | Clore manuellement la saison |
| /tournament_audit | Export CSV des essais, réservé aux organisateurs |

Les défis **calcul, mot maudit et code de la crypte** donnent respectivement
100, 130 et 160 points pour une réponse juste. Un joueur a au maximum
une tentative de chaque type par **jour UTC** ; le délai est de 100 secondes.
Chaque membre reçoit une question générée pour lui. Une tentative interrompue,
incorrecte ou expirée reste consommée jusqu'au lendemain.

Il y a **cinq divisions** : Bronze (0+), Argent (350+), Or (950+),
Diamant (2 200+) et Légende (4 500+). Les égalités sont affichées avec
le **même rang** et exigent un départage humain.

### Démarrer simplement la compétition

1. Compléter puis publier le fichier
   [TOURNAMENT_RULES_TEMPLATE.md](TOURNAMENT_RULES_TEMPLATE.md)
   sous forme de page HTTPS accessible à tous les participants.
2. Dans Discord, un administrateur utilise
   \`/tournament_start fin:2026-10-31 prix:1 000 € reglement:https://...\`
   (fin à la fin de la journée UTC).
3. Les joueurs utilisent **/competition → Participer → Défis**.
4. À la fin, l'administrateur utilise **/tournament_audit** puis vérifie
   les comptes, l'éligibilité, les résultats anormaux et les égalités avant
   d'annoncer un gagnant.

**Important :** aucune somme réelle n'est encaissée, misée ou versée par le
bot. Le **prix est annoncé et financé par l'organisateur**, pas garanti
par le logiciel. Une compétition avec enjeu réel nécessite un règlement
clair, un contrôle de triche, des critères d'âge et de pays admissibles,
ainsi qu'une vérification de conformité juridique par l'organisateur.
Les défis du bot seuls ne permettent **pas d'exclure tous les usages
d'IA, d'automatisation ou de comptes multiples** : pour un prix substantiel,
prévoyez une finale surveillée par un humain.


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
