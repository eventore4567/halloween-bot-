# 🎃 Nuit Hantée — le bot Discord d'Halloween

![Bannière animée](docs/banniere-accueil.gif)

Un bot Halloween **entièrement refait**, avec sa propre identité visuelle : des
**enseignes au néon animées** qui grésillent sur un vieux mur de briques, un seul format
de panneau pour tous les jeux, **74 emojis personnalisés** (dont 21 animés) dessinés par
le bot lui-même, des images générées (carte de profil, podium, roue, course, cartes à
collectionner), **17 jeux** et **27 succès** à débloquer.

## ✨ Ce qui rend le bot unique

- **Un seul format de panneau** (Components V2) : bannière animée → titre → sections →
  boutons → pied de page. Chaque jeu a sa couleur, tout le bot a la même allure.
- **Style néon unique** : chaque jeu a son enseigne lumineuse (titre en tubes néon,
  cadre, monstres dessinés en néon), qui clignote, grésille, crache des étincelles,
  avec du brouillard qui défile. Le même style habille la carte de profil, le podium,
  la roue et la course de balais.
- **Animé partout** : bannières GIF, emojis animés, comptes à rebours en direct,
  roue qui tourne réellement, course de sorcières animée, cartes qui se retournent,
  coffre et chaudron qui « s'ouvrent » et « bouillonnent ».
- **Emojis personnalisés automatiques** : au démarrage, le bot dessine et envoie ses
  74 emojis dans *Developer Portal → ton application → Emojis*. Ils marchent dans
  **tous les serveurs**, sans Nitro et sans prendre de place sur le serveur.
  Ils sont mis à jour tout seuls si le dessin change.
- **Images générées** : carte de profil avec ton avatar, niveau et XP ; podium du
  classement avec les avatars du top 3.

![Bannières](docs/apercu-bannieres.png)

![Le Grand Frisson](docs/apercu-frisson.png)

![Emojis](docs/apercu-emojis.png)

## 🕹️ Les jeux

| Commande | Jeu |
|---|---|
| `/jeux` | L'accueil : tous les jeux dans un menu, guide, coffre du jour |
| `/quiz` | **Le Grand Frisson**, le jeu télé hanté : 12 questions sur une **échelle de gains** jusqu'à 1 500 bonbons, 2 paliers, on peut encaisser à tout moment. Chaque question est une **vidéo GIF** (plateau néon, échelle, chrono qui se vide). 3 jokers : 50/50, **murmure du fantôme**, **vote du public**. Questions 3, 6 et 9 : **manche vidéo « Qui se cache dans l'ombre ? »** (une silhouette qui s'illumine). **700 questions** dont des questions de jeux vidéo |
| `/expedition` | **Expéditions** : envoie jusqu'à 3 de tes cartes de monstres en mission (30 min à 6 h). Plus ils sont rares, plus la mission réussit et plus le butin est gros |
| `/formule` | **La Formule** : déchiffre le code secret de 4 ingrédients du chaudron en 8 essais (façon Mastermind), la potion obtenue donne un effet bonus |
| `/roue` | **Roue du destin** animée, un tour gratuit toutes les 4 h, jackpot 1 000 |
| `/cartes` | **Cartes maudites** : 24 monstres à collectionner (4 raretés), révélation animée |
| `/maison` | **Maison hantée** : 4 pièces tirées au hasard parmi 10, 3 choix par pièce, trésors, pièges, monstres, 3 bougies de vie, une clé… et une **crypte** au trésor |
| `/course` | **Course de balais** : parie sur une des 4 sorcières, la course est un **GIF animé**, gain ×3,6 |
| `/rituel` | **Le Rituel** : mémorise la formule maudite qui s'efface, répète-la, elle s'allonge à chaque manche |
| `/reflexe` | **Réflexe du fantôme** : clique dès que le bouton passe au vert, 3 manches chronométrées |
| `/memoire` | **Mémoire d'outre-tombe** : 8 paires sur une grille de 16 boutons |
| `/chasse` | **Chasse aux fantômes** : creuse des tombes, double ton butin… évite les 3 Faucheuses |
| `/pendu` | **Le Pendu de la crypte** : 50 mots d'Halloween, indice, proposition du mot entier |
| `/sort @membre` | **Mauvais sort** : vole jusqu'à 8 % des bonbons d'un rival (60 % de réussite, sinon le sort se retourne contre toi). L'**amulette** de la boutique protège |
| `/duel @membre [mise]` | **Duel de monstres** : Vampire / Loup-garou / Chasseur en 2 manches gagnantes, mise en bonbons sécurisée |
| `/quotidien` | **Coffre du jour** avec série de 7 jours (booster offert au 7e jour) |
| `/boutique` | Jokers, boucliers, tickets, potions, amulettes, **titres** et **couleurs de profil** |
| `/succes` | **27 succès** avec barres de progression, chacun rapporte un bonus de bonbons |
| `/profil [membre]` | Carte de chasseur générée en néon, parties restantes, contenu du sac, expédition en cours |
| `/classement` | **Le Panthéon** : bonbons, total gagné, niveau, bonnes réponses, record du Grand Frisson, expéditions, cartes, duels |
| `/donner` | Offrir des bonbons (2 000 max par jour) |
| `/aide` | Guide du joueur |

### 👻 Événements de serveur

Dans le salon choisi par les organisateurs, quand le serveur est actif :

- **Sac de bonbons** : le premier qui clique gagne.
- **Quiz éclair** : première bonne réponse gagne, une seule tentative par personne.
- **Le Roi Citrouille** : boss collectif ! Ses PV s'adaptent au nombre de joueurs
  actifs, tout le monde frappe ensemble, récompenses selon les dégâts.

### 🔧 Commandes d'organisation (`Gérer le serveur`)

| Commande | Rôle |
|---|---|
| `/admin salon` | Salon des apparitions |
| `/admin apparitions` | Activer/désactiver, fréquence (tous les N messages, max 1 toutes les 4 min) |
| `/admin lancer` | Lancer tout de suite un sac, un quiz éclair ou le boss |
| `/admin bonbons` | Ajouter / retirer des bonbons à un membre |
| `/admin emojis` | Re-synchroniser les emojis personnalisés |

![Profil](docs/apercu-profil.png)

## 🚀 Installation

1. **Developer Portal** → ton application → *Bot* : copie le token.
   Aucun « Privileged Intent » n'est nécessaire.
2. Invite le bot avec les scopes `bot` et `applications.commands` et ces permissions :
   Voir les salons, Envoyer des messages, Intégrer des liens, Joindre des fichiers,
   Lire l'historique, Utiliser des emojis externes.
   Lien prêt à l'emploi (remplace `APP_ID`) :
   `https://discord.com/oauth2/authorize?client_id=APP_ID&scope=bot+applications.commands&permissions=379904`
3. Sur Railway (ou ailleurs) :
   - variable secrète **`discord_token`** (ou `DISCORD_TOKEN`) ;
   - un **volume** monté sur `/data` (sinon les bonbons sont effacés à chaque déploiement) ;
   - commande de démarrage : `python3 main.py` (déjà dans `railway.toml` et `Procfile`).
4. Au premier démarrage, le bot envoie ses emojis (environ 1 minute), puis tout
   s'affiche avec les emojis personnalisés. En attendant, des emojis classiques
   sont utilisés automatiquement.
5. Sur ton serveur : `/admin salon` pour activer les apparitions, puis `/jeux` !

Variables optionnelles : `DATA_DIR` (dossier de la base, `/data` par défaut s'il existe),
`DATABASE_PATH`, `BOT_TIMEZONE` (par défaut `Europe/Paris`, pour la remise à zéro de minuit).

> La nouvelle base s'appelle `nuit_hantee.sqlite3` : le classement repart à zéro
> avec ce nouveau bot. Chaque serveur a sa propre économie.

## 🧪 Tests

```sh
pip install -r requirements.txt
python -m compileall -q main.py halloween tests
python -m unittest discover -s tests -v
```

Les tests cliquent dans chaque jeu comme un joueur (sans connexion à Discord),
vérifient la base de données, la banque de questions, les images, et que chaque
panneau respecte les limites de Discord (40 composants, 4 000 caractères), même avec
les emojis personnalisés.

## 📂 Structure

```
main.py                     démarrage du bot
halloween/
  ui.py                     LE format de panneau unique + navigation persistante
  db.py                     SQLite (transactions, anti-solde négatif)
  emojis.py                 envoi et utilisation des emojis d'application
  config.py                 équilibrage : gains, limites, boutique, Grand Frisson, roue, succès
  rewards.py                bonbons + XP + passage de niveau
  art/                      dessin des emojis, bannières GIF, cartes et images
  content/                  questions du quiz, mots du pendu, potions, cartes
  cogs/                     un fichier par jeu
assets/fonts/               polices libres (OFL / Apache 2.0)
tests/
```

Le jeu utilise uniquement des bonbons virtuels : **aucun argent réel ni mise d'argent**.
Les polices Luckiest Guy (Apache 2.0), Lilita One, Fredoka et Tilt Neon (SIL OFL)
sont incluses avec leurs licences dans `assets/fonts/`.
