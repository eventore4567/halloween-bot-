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
| /quiz | Quiz des ténèbres (4 catégories, 4 difficultés, 4 réponses) |
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
| /film_horreur | Reconnaître un film d'horreur sur une image publique |
| /jeux | Cabinet des sept mini-jeux Halloween avec boutons |\n| /setup | Panneau unique pour salon, rôle, fréquence et inscriptions |

## 🕹️ Le cabinet des jeux Halloween

**/jeux** ouvre un panneau illustré comme CRYPT CUP, avec **sept mini-jeux**
disponibles sans multiplier les commandes slash :

- 🔮 **Mémoire des runes** : mémorise quatre symboles et reproduis l'ordre après la disparition du modèle.
- 👻 **Réflexe du fantôme** : attends son apparition puis clique au plus vite.
- 🗝️ **Labyrinthe maudit** : trois portes à trouver à l'aide d'indices.
- 🎃 **Chaudron magique** : trois ingrédients à déduire d'énigmes.
- ⚰️ **Coffres hantés** : choisis un coffre, parfois vide, parfois rempli de bonbons.
- 🎲 **Dés du démon** : devine si le prochain lancer sera plus haut ou plus bas.
- 🦇 **Chasse spectrale** : retrouve le fantôme caché derrière une tombe.

Chaque partie est individuelle (panneau éphémère), avec 85 secondes maximum,
des boutons Discord interactifs et une récompense de bonbons virtuels. Une
protection SQLite limite les répétitions à **une partie toutes les deux
minutes par jeu**. Les gains sont accordés une seule fois par partie.

**Aucun mini-jeu, hasard ou bonbon ne modifie les points de la compétition
CRYPT CUP offrant éventuellement un prix réel.** Les scores du tournoi restent
réservés aux épreuves de réflexion individuelles prévues par son règlement.

Le bouton **Les jeux** du panneau /halloween ouvre désormais le même cabinet.
Les commandes /quiz et /film_horreur ont reçu un affichage plus compact, sans
double panneau gris ni description d'image provoquant le badge ALT. La
reconnaissance des films utilise des images Wikimedia Commons dont les
sources sont affichées après la réponse.

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

Le chargement des emojis de l'application nécessite discord.py 2.6 ou plus récent.
Après avoir ajouté des emojis, redémarre simplement le service Railway.
### 🪦 `/competition` — une scène Halloween sans cadre gris

La commande présente une image horizontale (1280 × 840), calculée à partir
des vrais scores et manches. Les cinq boutons **Participer, Mes défis,
Top 10, Mon rang, Règlement** se trouvent sur une **seule ligne**, directement
sous le visuel, sans conteneur Discord autour. Cela supprime le fond gris
supplémentaire, les grosses marges et la barre violette extérieure.

La structure envoyée à Discord est : **MediaGallery (type 12) + ActionRow
(type 1)**. Le message n'utilise plus de `Container` (type 17).

**Limite officielle de Discord :** une image ne peut pas avoir de zones
cliquables arbitraires ni de boutons superposés. Les boutons restent
authentiquement interactifs et intégrés au même message, mais pas dans
l'image. Pour un fond entièrement personnalisable avec des boutons
positionnés librement, il faudrait une interface web.

Les chiffres et compteurs dans l'image sont une photographie au moment de
`/competition` : il faut relancer la commande pour les actualiser.

**Pack emoji de l'application :** lors du premier démarrage, le bot utilise
`discord.py` pour téléverser **10 emojis originaux 128×128** sur la même
application dans le Discord Developer Portal :
`pumpkin`, `ghost`, `bat`, `skull`, `trophy`, `key`, `book`,
`candy`, `crown` et `clock`. Les emojis sont générés localement
par Pillow, sans copier ceux d'un serveur. Les noms déjà présents ne sont
jamais écrasés ; un redémarrage est donc sans danger. S'ils ne peuvent pas
être publiés (permissions/erreur API), le bot continue avec des emojis
Unicode standard et journalise les erreurs, sans interrompre les commandes.

Aucune donnée de saison, bonbon, compte joueur ou ancienne commande n'est
supprimée par cette modification.

## 🏆 CRYPT CUP — la compétition automatique

**Une interface unique conçue avec les composants Discord V2** : vraie mise en page,
sections encadrées, couleurs violet / ambre / jade, tableau d'honneur, boutons.
La compétition ne reprend pas le style d'autres bots.

### Lancer en 30 secondes

1. **/setup** (réservé aux membres qui peuvent Gérer le serveur).
2. Choisir un **salon textuel** et un **rôle à mentionner**.
3. Choisir les annonces **toutes les 30, 60 ou 120 minutes**.
4. Choisir **10 ou 30 minutes pour s'inscrire**.
5. Cliquer sur **Valider & programmer**.

La saison démarre automatiquement et se termine à Halloween (UTC) ou,
après Halloween, dans 14 jours. Le bot publie directement une annonce dans
le salon choisi, **en mentionnant uniquement le rôle configuré**.
Les membres cliquent sur **INSCRIRE MON NOM**. À la fin des inscriptions,
la manche démarre automatiquement et dure **10 minutes**. Le podium de manche
se met à jour une fois le temps écoulé. Tout fonctionne après un redémarrage.

### Commandes utiles (liste réduite)

| Commande | Fonction |
|---|---|
| /competition | Vrai centre de compétition CRYPT CUP, avec inscriptions, défis, Top 10 et règlement |
| /challenge | Les défis disponibles **pendant une manche**, réservé aux inscrits |
| /leaderboard | Classement de saison par défaut, autres statistiques accessibles |
| /quiz | Quiz public à difficultés facile, moyen, difficile, expert |
| /film_horreur | Reconnaitre un film d'horreur à l'aide d'une image de Wikimedia Commons |
| /setup | Configuration et **rapport CSV** réservé aux responsables |

Les **trois épreuves individuelles** rapportent 100, 130 et 160 points.
Une seule épreuve est comptabilisée par manche, **trois au maximum par jour UTC**.
Les joueurs disposent de 100 secondes maximum. Il faut s'inscrire pendant
la fenêtre publique pour pouvoir marquer des points dans la manche.

Les **bonbons, la ferme, les duels aléatoires, le quiz communautaire et les
images de films** donnent des récompenses virtuelles mais **aucun point** pour
le classement réel. Les points officiels sont enregistrés dans une base SQLite
avec historique des tentatives, contrôles anti-double paiement et score
réservé aux inscrits.

Les divisions sont **Bronze, Argent, Or, Diamant, Légende**. Les égalités
obtiennent le même rang. Les résultats restent provisoires jusqu'à validation
par un organisateur.

### 🎬 Devine le film d'horreur

Le bot utilise une sélection de photogrammes de films anciens disponibles sur
Wikimedia Commons. Les sources sont données dans le message **après** la
question. Il n'affiche pas les titres ou les liens de source pendant le jeu.
Le corpus est volontairement limité aux images dont la page de fichier existe,
avec un niveau facile/moyen/difficile. Les règles de réutilisation et droits
d'auteur peuvent varier selon les pays.

### 💰 Si un prix de 1 000 € est annoncé

**Le prix est offert par l'organisateur, pas par le bot.** Dans /setup,
ouvrir **Prix & règles**, remplir le montant annoncé et une URL HTTPS vers
un règlement officiel. Sans ce règlement, le lancement est bloqué si un
prix est mentionné. L'organisateur doit vérifier les conditions d'âge,
l'éligibilité, le traitement des données et la légalité locale, et effectuer
une finale surveillée avant de verser un prix important.

Le rapport complet est récupérable via le bouton **Rapport final** du /setup :
il contient les essais et les points. Aucun paiement automatique, mise d'argent
ou choix définitif du gagnant n'est programmé.


## 🌾 La ferme de citrouilles

Ouvre **/farm** : trois graines sont proposées, avec différentes durées et récompenses. Récolte quand la plantation est prête, puis améliore ton potager jusqu'au niveau 5 (bonus de rendement). Tout est sauvegardé en SQLite, de manière transactionnelle.

## 🔧 Lancer le bot

Python 3.11+ et **discord.py 2.6+** requis.

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
- `halloween_bot/admin.py` : configuration du salon, rôle, durée, fréquence et rapport des résultats.\n- `halloween_bot/round_store.py` et `halloween_bot/rounds.py` : manches automatiques persistantes.\n- `halloween_bot/quiz_content.py` et `halloween_bot/quiz_games.py` : quiz à difficultés et films.\n- `halloween_bot/visuals.py` : interface originale CRYPT CUP en Discord Components V2.
- `halloween_bot/content.py` : questions, objets, décors.
- `halloween_bot/common.py` : messages, mises en forme, composants communs.

Le jeu utilise uniquement des bonbons virtuels et n'intègre **ni argent réel, ni mises monétaires**.
