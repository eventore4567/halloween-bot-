# BloxHub

Hub d'informations et de progression pour **Blox Fruits**, en français.
Aucun système de clé, aucune publicité, aucune automatisation de jeu : le hub **lit et affiche**
tes informations et te dit ce qu'il te manque pour chaque objectif.

Version : **1.1.0**

> Ce projet vit sur la branche dédiée **`bloxhub`**, sans aucun fichier du bot Halloween (branche `main`).

## Lancement

Colle cette ligne dans ton exécuteur :

```lua
loadstring(game:HttpGet("https://raw.githubusercontent.com/eventore4567/halloween-bot-/refs/heads/bloxhub/loader.lua"))()
```

Pour un fork, définis `getgenv().BloxHubBase = "https://raw.githubusercontent.com/<toi>/<dépôt>/refs/heads/<branche>/"` avant la ligne.

## Ce qui est inclus et ce qui ne l'est pas

| Fonction | État |
| --- | --- |
| Dashboard, Progression, Équipements, suivi des Races V2 / V3 / V4, lecture d'inventaire, Paramètres, Diagnostic, recherche | ✅ inclus (suivi, lecture seule) |
| Auto Farm, Auto Boss, Auto Sword, Auto Mastery, Auto Quest | ❌ **non inclus** |

BloxHub ne contrôle jamais ton personnage. Les fonctions « Auto » jouent à ta place : c'est de la triche selon les
règles de Roblox et de Blox Fruits, et elles pèsent sur les autres joueurs (boss et drops partagés). Elles ne sont
pas fournies, et aucun bouton ne fait semblant de les activer. La page **Automatisation** du hub le rappelle.

## Risques

- Lancer un script avec un exécuteur (Opiumware compris) **enfreint les conditions d'utilisation de Roblox**, même pour un hub en lecture seule.
- Roblox et Blox Fruits ont des systèmes de détection. **Aucun script n'est indétectable**, et BloxHub n'essaie pas de se cacher.
- Sanctions possibles : avertissement, bannissement temporaire ou définitif.
- La lecture d'inventaire envoie une requête au serveur du jeu (lecture seule, 1 fois / 15 s max). Désactivable dans Paramètres → Modules.
- Pour ne rien risquer sur ton compte principal, utilise un compte secondaire.

## Contrôles

| Action | Comment |
| --- | --- |
| Déplacer | glisser la barre de titre (la fenêtre reste toujours accrochée à l'écran) |
| Réduire | bouton `–` (seule la barre de titre reste) |
| Masquer | bouton `×` |
| Rouvrir | bouton flottant `◆ BloxHub` (déplaçable) ou **RightShift** (modifiable) |
| Arrêt d'urgence | Paramètres → `⏻ Arrêt d'urgence`, ou `getgenv().BloxHub.Shutdown()` |

## Sections

- **Dashboard** : niveau, Sea (déduite du PlaceId), race, Beli, Fragments, fruit, arme en main et sa maîtrise, état des modules.
- **Progression** : objectifs adaptés à ton niveau et ta Sea, conditions de déblocage, maîtrises des objets de ton sac, fiches boss, guide des trois Seas.
- **Équipements** : Pole V1, Pole V2, Saber, Rengoku, CDK, Godhuman, Skull Guitar — prérequis (✓ / ✗ / ?), étapes, progression en %, ressources manquantes chiffrées.
- **Races** : Angel V2 / V3 / V4, Human, Shark, Mink (Rabbit), Cyborg, Ghoul.
- **Paramètres** : notifications, animations, taille, intervalle de rafraîchissement, touche, activation de chaque module, recharger, réinitialiser, arrêt d'urgence.
- **Diagnostic** : exécuteur, résultat des tests d'API, état des modules, tâches et connexions actives, mémoire, journal technique (copiable).
- **Automatisation** : liste honnête des fonctions non incluses et des risques (aucun interrupteur factice).
- **Recherche** (en haut de la barre latérale) : trouve un équipement, un boss, une Sea, un réglage…

### Ce qui est vérifié automatiquement, ce qui ne l'est pas

- ✓ / ✗ : niveau, Beli, Fragments, Sea, race, objets présents dans ton sac ou en main, maîtrise des objets du sac.
- Matériaux (Bones, Ectoplasm, Fish Tail…) et objets rangés : bouton **Analyser mon inventaire**. Il envoie
  la même requête en lecture seule que l'inventaire du jeu (`getInventory`), au maximum une fois toutes les 15 s,
  avec un délai maximal de 10 s. Désactivable dans les paramètres.
- `?` : ce qu'un script ne peut pas lire de façon fiable (version V2/V3/V4 de la race, quêtes terminées comme Don Swan ou le Colisée). À confirmer en jeu.

Les données de jeu ont été vérifiées le 17/10/2026 à partir de guides publics (wiki Fandom Blox Fruits, KeenGamer,
Beebom, Deltia's Gaming, Pro Game Guides…). Quand les sources se contredisent (Pole V2, maîtrise CDK 350 ou 400,
pleine lune pour la V4, taux de drop…), le hub l'indique par un `⚠` au lieu de trancher.

## Stabilité

- **Un seul hub à la fois** : relancer la commande arrête proprement l'instance précédente ; un verrou empêche deux chargements simultanés.
- **Modules isolés** : chaque module est initialisé dans un `pcall`. Un module en erreur est marqué « erreur » et le reste fonctionne. Seuls les modules de base (interface, config, tâches…) sont obligatoires.
- **Aucune boucle libre** : toutes les boucles passent par `src/tasks.lua` (nom unique, intervalle minimal, arrêt automatique après 5 erreurs). Le Dashboard ne se rafraîchit que s'il est affiché (toutes les 2 s par défaut) ; rien ne tourne quand la fenêtre est réduite ou masquée.
- **Délais d'attente** : téléchargement des modules (20 s), chargement du jeu (30 s), lecture d'inventaire (10 s).
- **Nettoyage** : toutes les connexions passent par `Tasks:connect` et sont coupées à l'arrêt ; celles des éléments détruits sont purgées.
- **Interface persistante** : `ResetOnSpawn = false`, rattachement automatique si l'interface est retirée de l'écran.
- **Journal technique** : 300 dernières entrées, avec la pile d'appel des erreurs (page Diagnostic).

## Compatibilité

Le hub ne suppose aucune API d'exécuteur : `src/compat.lua` teste au démarrage ce qui est disponible et désactive proprement ce qui ne l'est pas.

| API | Utilisation | Si absente |
| --- | --- | --- |
| `loadstring`, `game:HttpGet` | chargement | indispensables (message clair sinon) |
| `getgenv` | anti double lancement | repli sur `_G` |
| `gethui` | interface protégée | repli sur `CoreGui`, puis `PlayerGui` |
| `writefile` / `readfile` / `isfolder` / `makefolder` | sauvegarde de la config | config gardée en mémoire pour la session (testée réellement par écriture + relecture) |
| `setclipboard` | copier le journal | bouton masqué |
| `identifyexecutor` | affichage dans Diagnostic | « inconnu » |

Le hub ne contourne aucune protection, ne collecte aucun identifiant, cookie ou mot de passe et n'envoie rien ailleurs que sur GitHub (téléchargement de ses propres fichiers).

## Structure

```
(branche bloxhub)
  loader.lua            chargeur (versions, sources, ordre des modules, arrêt / rechargement)
  src/
    compat.lua          détection et test des API de l'exécuteur
    diagnostics.lua     journal technique, exécution protégée
    tasks.lua           tâches nommées, délais, connexions, arrêt d'urgence
    config.lua          paramètres par défaut, sauvegarde JSON
    ui.lua              fenêtre, navigation, recherche, composants
    notifications.lua   notifications discrètes
    player_info.lua     lecture des données du joueur
    requirements.lua    évaluation des prérequis et rendu des fiches
    inventory.lua       lecture d'inventaire à la demande
    dashboard.lua       page Dashboard
    progression.lua     page Progression (objectifs, boss, Seas)
    equipment.lua       page Équipements
    races.lua           page Races
    automation.lua      page Automatisation (état et risques)
    settings.lua        pages Paramètres et Diagnostic
  tests/
    mock_roblox.luau    environnement Roblox simulé
    run_tests.luau      scénarios de test
    run.sh              lance compilation + tests
```

Dépendances : aucune bibliothèque externe côté Roblox. Pour les tests : [Luau](https://github.com/luau-lang/luau) (`luau`, `luau-compile`) et Python 3.

## Tests

```sh
sh tests/run.sh          # LUAU / LUAU_COMPILE pour indiquer les binaires
```

Les tests compilent chaque fichier avec `luau-compile`, puis exécutent le **vrai code du hub** dans un Roblox simulé
qui lève les mêmes erreurs que Roblox sur une propriété inconnue, un mauvais type, un `Enum` inexistant ou un `Parent`
verrouillé. Ils couvrent : chargement, chaque page, navigation, cartes, recherche, interrupteurs et sélecteurs,
réduire / masquer / rouvrir / raccourci / déplacement, sauvegarde de la config, double lancement, rechargement,
arrêt d'urgence, modules cassés ou désactivés, exécuteur sans fichiers ni `gethui` ni `CoreGui`, jeu non reconnu,
inventaire bloqué (délai), panne réseau, source personnalisée, page Automatisation sans faux boutons, fuites d'instances et de connexions, nombre de
rafraîchissements sur 60 s.

**Limite** : ce n'est pas Roblox. Le rendu visuel réel, les polices et le comportement exact d'Opiumware ne peuvent
être vérifiés qu'en jeu. Si quelque chose ne va pas, ouvre la page Diagnostic et copie le journal.

## Versions

- **1.1.0** — projet déplacé sur la branche dédiée `bloxhub` ; page Automatisation (fonctions non incluses + risques) ; barre latérale groupée SUIVI / AUTOMATISATION / OUTILS.
- **1.0.0** — première version : Dashboard, Progression, Équipements, Races, Paramètres, Diagnostic, recherche.
