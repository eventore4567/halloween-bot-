"""Twelve Halloween games with deterministic, testable state machines.

All rewards are virtual candy and NEVER affect the real-prize CRYPT CUP score.
No bets, paid currency, cash-out, or negative candy balances are involved.
A session has one owner, an 85-second deadline, and a single terminal result.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

MODES = {
    "memoire":   ("Mémoire des runes", "Retrouve quatre symboles dans l'ordre.", 160, "book"),
    "reflexe":   ("Réflexe du fantôme", "Clique dès que le fantôme apparaît.", 170, "ghost"),
    "labyrinthe":("Labyrinthe maudit", "Résous trois portes grâce aux indices.", 150, "key"),
    "chaudron":  ("Chaudron magique", "Choisis les ingrédients des trois énigmes.", 145, "pumpkin"),
    "coffres":   ("Coffres hantés", "Ouvre un coffre : trésor ou poussière.", 180, "candy"),
    "des":       ("Dés du démon", "Trouve si son dé sera plus haut ou plus bas.", 125, "skull"),
    "fantomes":  ("Chasse spectrale", "Choisis la tombe où se cache un fantôme.", 135, "bat"),
    "ombres":    ("L'intrus des ombres", "Repère le symbole qui brise le rituel.", 140, "ghost"),
    "bougies":   ("Bougies de la crypte", "Résous trois calculs avant l'extinction.", 155, "clock"),
    "vampire":   ("Procès du vampire", "Déjoue trois pièges grâce aux indices.", 165, "skull"),
    "tarot":     ("Tarot interdit", "Devine la couleur de la prochaine carte.", 130, "book"),
    "crane":     ("Crâne maudit", "Bats le gardien dans un duel de symboles.", 145, "pumpkin"),
}
DIFFICULTIES = {
    "facile": ("🌱 Facile", 0.80),
    "moyen": ("🔥 Moyen", 1.00),
    "difficile": ("💀 Difficile", 1.30),
    "cauchemar": ("👑 Cauchemar", 1.60),
}
SYMBOLS = ("🌙", "🦇", "🎃", "🕯️")
POTION_OPTIONS = ("🕸️ Toile", "🎃 Citrouille", "🦇 Chauve-souris", "🌙 Lune")
POTION_CLUES = (
    ("Je suis tissée par une araignée.", 0),
    ("Je suis un fruit orange sculpté en octobre.", 1),
    ("Je vole la nuit, mais je ne suis pas un oiseau.", 2),
    ("Je brille au-dessus du château quand la nuit tombe.", 3),
    ("Je suis collante et je capture les insectes.", 0),
    ("Ma lumière éclaire les loups-garous.", 3),
)
MAZE_OPTIONS = ("🌙 Lune", "🦇 Chauve-souris", "🕯️ Chandelle")
MAZE_CLUES = (
    ("Je change de forme sans quitter le ciel.", 0),
    ("Je dors la tête en bas dans une grotte.", 1),
    ("Je brûle sans être le soleil.", 2),
    ("Je n'ai pas de plumes, mais je peux voler.", 1),
    ("Je veille dans le ciel lorsque le soleil s'endort.", 0),
    ("Je réchauffe la crypte avec une petite flamme.", 2),
)
VAMPIRE_OPTIONS = ("🧄 Ail", "🪞 Miroir", "☀️ Soleil", "🩸 Sang")
VAMPIRE_CLUES = (
    ("Je parfume les cuisines et repousse les crocs.", 0),
    ("Je renvoie ton visage, mais jamais celui du vampire.", 1),
    ("Je transforme le vampire en poussière au lever du jour.", 2),
    ("Je coule dans les veines et attire les créatures de la nuit.", 3),
    ("Mes gousses protègent la porte de la crypte.", 0),
    ("Je brille dans le ciel et force le vampire à dormir.", 2),
)
SHADOW_SYMBOLS = ("🎃", "👻", "🦇", "💀")
TAROT_COLORS = ("🟣 Violette", "🟠 Orange", "⚫ Noire")
SKULL_MOVES = ("🎃 Citrouille", "🦇 Chauve-souris", "💀 Crâne")
COFFIN_REWARDS = (0, 50, 100, 180)
TTL_SECONDS = 85


@dataclass(frozen=True)
class GameMove:
    status: str
    message: str
    reward: int = 0


class MiniSession:
    """One-shot owner-bound logic. UI enforces user/guild, this enforces state."""

    def __init__(self, mode: str, *, difficulty="moyen", now=None, rng=None):
        if mode not in MODES:
            raise ValueError(f"Unknown minigame: {mode}")
        if difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {difficulty}")
        self.mode = mode
        self.difficulty = difficulty
        self.rng = rng or random.SystemRandom()
        self.started_at = time.monotonic() if now is None else float(now)
        self.deadline = self.started_at + TTL_SECONDS
        self.ready_at = self.started_at
        self.done = False
        self.success = False
        self.step = 0
        self.last = ""
        skill_steps = {"facile": 2, "moyen": 3, "difficile": 4, "cauchemar": 5}[difficulty]
        if mode == "memoire":
            self.target_steps = skill_steps + 1
            self.sequence = tuple(
                self.rng.randrange(len(SYMBOLS)) for _ in range(self.target_steps)
            )
            self.ready_at += 6
        elif mode == "reflexe":
            self.ready_at += self.rng.randint(3, 6)
        elif mode == "labyrinthe":
            self.target_steps = skill_steps
            self.puzzles = tuple(self.rng.sample(MAZE_CLUES, self.target_steps))
        elif mode == "chaudron":
            self.target_steps = skill_steps
            self.puzzles = tuple(self.rng.sample(POTION_CLUES, self.target_steps))
        elif mode == "coffres":
            self.chest_rewards = tuple(self.rng.sample(COFFIN_REWARDS, 4))
        elif mode == "des":
            self.demon_die = self.rng.randint(2, 5)
        elif mode == "fantomes":
            self.hidden_ghost = self.rng.randrange(4)
        elif mode == "ombres":
            self.shadow_base = self.rng.randrange(len(SHADOW_SYMBOLS))
            self.shadow_odd = self.rng.randrange(4)
            choices = [SHADOW_SYMBOLS[self.shadow_base]] * 4
            choices[self.shadow_odd] = SHADOW_SYMBOLS[(self.shadow_base + self.rng.randrange(1, 4)) % 4]
            self.shadow_choices = tuple(choices)
        elif mode == "bougies":
            self.target_steps = skill_steps
            ceiling = {"facile": 8, "moyen": 12, "difficile": 20, "cauchemar": 30}[difficulty]
            puzzles = []
            for _ in range(self.target_steps):
                left, right = self.rng.randint(2, ceiling), self.rng.randint(1, ceiling)
                answer = left + right
                values = {answer}
                while len(values) < 4:
                    values.add(max(1, answer + self.rng.choice((-4, -3, -2, -1, 1, 2, 3, 4))))
                options = list(values)
                self.rng.shuffle(options)
                puzzles.append((f"{left} + {right} = ?", tuple(options), options.index(answer)))
            self.number_puzzles = tuple(puzzles)
        elif mode == "vampire":
            self.target_steps = skill_steps
            self.puzzles = tuple(self.rng.sample(VAMPIRE_CLUES, self.target_steps))
        elif mode == "tarot":
            self.tarot_color = self.rng.randrange(3)
        elif mode == "crane":
            self.skull_move = self.rng.randrange(3)

    def options(self) -> tuple[str, ...]:
        return {
            "memoire": SYMBOLS,
            "reflexe": ("👻 Attraper !",),
            "labyrinthe": MAZE_OPTIONS,
            "chaudron": POTION_OPTIONS,
            "coffres": ("⚰️ Tombe I", "⚰️ Tombe II", "⚰️ Tombe III", "⚰️ Tombe IV"),
            "des": ("🎲 Plus haut", "🎲 Plus bas"),
            "fantomes": ("🪦 Tombe I", "🪦 Tombe II", "🪦 Tombe III", "🪦 Tombe IV"),
            "ombres": self.shadow_choices if self.mode == "ombres" else (),
            "bougies": tuple(str(value) for value in self.number_puzzles[self.step][1]) if self.mode == "bougies" else (),
            "vampire": VAMPIRE_OPTIONS,
            "tarot": TAROT_COLORS,
            "crane": SKULL_MOVES,
        }[self.mode]

    def prompt(self, now=None) -> str:
        now = time.monotonic() if now is None else float(now)
        if self.done:
            return self.last
        if self.mode == "memoire":
            if now < self.ready_at:
                sequence = "  ".join(SYMBOLS[index] for index in self.sequence)
                return (
                    f"🔮 **Mémorise l'ordre :** {sequence}\n"
                    f"Il disparaît dans **{max(1, int(self.ready_at-now+0.99))} secondes**."
                )
            return f"🔮 **Répète la séquence !** Symbole **{self.step + 1}/{self.target_steps}**."
        if self.mode == "reflexe":
            if now < self.ready_at:
                return "🌫️ Le fantôme se cache… attends son apparition !"
            return "👻 **MAINTENANT !** Attrape le fantôme avant qu'il disparaisse !"
        if self.mode == "labyrinthe":
            return (
                f"🚪 **Porte {self.step+1}/{self.target_steps}**\n"
                f"Indice : *{self.puzzles[self.step][0]}*\n"
                "Choisis la porte associée à l'énigme."
            )
        if self.mode == "chaudron":
            return (
                f"🧪 **Ingrédient {self.step+1}/{self.target_steps}**\n"
                f"Le grimoire dit : *{self.puzzles[self.step][0]}*\n"
                "Ajoute le bon ingrédient au chaudron."
            )
        if self.mode == "coffres":
            return "⚰️ **Quatre coffres, un seul choix.** Aucun bonbon n'est misé."
        if self.mode == "des":
            return (
                f"🎲 Le démon a lancé **{self.demon_die}**.\n"
                "Son prochain dé sera-t-il **plus haut** ou **plus bas** ? "
                "Une égalité donne un lot de consolation."
            )
        if self.mode == "fantomes":
            return "👻 Un fantôme s'est glissé dans l'une des quatre tombes…"
        if self.mode == "ombres":
            return "🌑 **Un symbole est différent des trois autres.** Trouve l'intrus."
        if self.mode == "bougies":
            return f"🕯️ **Calcul {self.step + 1}/{self.target_steps}** · {self.number_puzzles[self.step][0]}"
        if self.mode == "vampire":
            return (
                f"🧛 **Piège {self.step + 1}/{self.target_steps}**\n"
                f"Indice : *{self.puzzles[self.step][0]}*"
            )
        if self.mode == "tarot":
            return "🔮 La prochaine carte sera-t-elle violette, orange ou noire ?"
        return "💀 Citrouille bat Crâne, Crâne bat Chauve-souris, Chauve-souris bat Citrouille."

    def available(self, now=None) -> bool:
        now = time.monotonic() if now is None else float(now)
        return not self.done and self.ready_at <= now < self.deadline

    def choose(self, index: int, *, now=None) -> GameMove:
        now = time.monotonic() if now is None else float(now)
        if self.done:
            return GameMove("used", "Cette partie est déjà terminée.")
        if now >= self.deadline:
            self.done = True
            self.last = "⌛ Les portes du sanctuaire se sont refermées."
            return GameMove("timeout", self.last)
        if now < self.ready_at:
            return GameMove("waiting", "Attends le signal avant de jouer.")
        if not isinstance(index, int) or not 0 <= index < len(self.options()):
            return GameMove("invalid", "Ce choix n'existe pas.")

        if self.mode in ("memoire", "labyrinthe", "chaudron", "vampire", "bougies"):
            if self.mode == "memoire":
                correct = self.sequence[self.step]
            elif self.mode == "bougies":
                correct = self.number_puzzles[self.step][2]
            else:
                correct = self.puzzles[self.step][1]
            if index != correct:
                self.done = True
                self.last = (
                    "💀 Mauvaise rune ! L'ordre était : "
                    + "  ".join(SYMBOLS[i] for i in self.sequence)
                    if self.mode == "memoire" else
                    f"💀 Mauvais choix ! La bonne réponse était "
                    f"**{self.options()[correct]}**."
                )
                return GameMove("lost", self.last)
            self.step += 1
            if self.step < self.target_steps:
                self.last = "✅ Bonne réponse. La prochaine étape est ouverte !"
                return GameMove("progress", self.last)
            return self._win(self.reward(MODES[self.mode][2]),
                             "✨ **Rituel accompli !** Tu as réussi toutes les étapes.")

        if self.mode == "reflexe":
            reaction = now - self.ready_at
            if reaction <= 1.2:
                points = 170
                comment = "⚡ Réflexe surnaturel !"
            elif reaction <= 3:
                points = 115
                comment = "👻 Excellent réflexe !"
            elif reaction <= 9:
                points = 65
                comment = "🕯️ Le fantôme a failli s'échapper."
            else:
                points = 25
                comment = "🌫️ Juste à temps !"
            return self._win(self.reward(points),comment)

        if self.mode == "coffres":
            reward = self.chest_rewards[index]
            if reward == 0:
                return self._lose("🕸️ Ce coffre ne contient que de la poussière !")
            return self._win(self.reward(reward), "🎁 Le coffre s'ouvre sur un trésor !")

        if self.mode == "des":
            result = self.rng.randint(1, 6)
            if result == self.demon_die:
                return self._win(self.reward(25), f"🎲 **Égalité : {result}.** Lot de consolation !")
            correct = (result > self.demon_die and index == 0) or (
                result < self.demon_die and index == 1
            )
            if correct:
                return self._win(self.reward(125),f"🎲 **Le dé affiche {result} !** Bonne prédiction.")
            return self._lose(f"💀 **Le dé affiche {result}.** Mauvaise prédiction.")

        if self.mode == "fantomes":
            if index == self.hidden_ghost:
                return self._win(self.reward(135),"👻 Tu as capturé le fantôme derrière la tombe !")
            return self._lose(
                f"🌫️ Rien ici. Le fantôme se cachait derrière "
                f"**{self.options()[self.hidden_ghost]}**."
            )
        if self.mode == "ombres":
            if index == self.shadow_odd:
                return self._win(self.reward(140), "🌑 Ton regard a percé l'illusion !")
            return self._lose(f"🕸️ L'intrus était le symbole **{self.shadow_odd + 1}**.")
        if self.mode == "tarot":
            if index == self.tarot_color:
                return self._win(self.reward(130), "🔮 La carte obéit à ta prédiction !")
            return self._lose(f"🌫️ La carte était **{TAROT_COLORS[self.tarot_color]}**.")
        # Circular duel: each move defeats the next one (0>2, 2>1, 1>0).
        if index == self.skull_move:
            return self._win(self.reward(30), "⚖️ Égalité : le gardien t'accorde quelques bonbons.")
        wins = (index == 0 and self.skull_move == 2) or (index == 2 and self.skull_move == 1) or (index == 1 and self.skull_move == 0)
        if wins:
            return self._win(self.reward(145), f"⚔️ Le gardien avait choisi **{SKULL_MOVES[self.skull_move]}**. Victoire !")
        return self._lose(f"💀 Le gardien avait choisi **{SKULL_MOVES[self.skull_move]}**.")

    def reward(self, base: int) -> int:
        """Difficulty changes virtual rewards without touching competition points."""
        return max(1, round(base * DIFFICULTIES[self.difficulty][1]))

    def expire(self) -> None:
        self.done = True
        self.last = "⌛ La partie est terminée : le portail a disparu."

    def _win(self,reward,message):
        self.done = True
        self.success = True
        self.last = message
        return GameMove("won",message,reward)

    def _lose(self,message):
        self.done = True
        self.last = message
        return GameMove("lost",message)
