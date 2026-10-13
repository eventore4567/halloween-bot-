"""La Série hantée — season 1: « Les Disparus de Brumeval ».

One episode a night. Members of the server play the three main parts:
{hero} (le héros), {suspect} (le suspect) and {victim} (la disparue / le disparu).
Every episode ends on a choice the whole server votes on; the winning choice is
told at the start of the next episode and pushes one of four leanings
(courage, lumiere, savoir, soupcon), which decide the finale.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LEANINGS = ("courage", "lumiere", "savoir", "soupcon")


@dataclass(frozen=True)
class Choice:
    label: str
    emoji: str
    leaning: str
    outcome: str  # told at the start of the next episode


@dataclass(frozen=True)
class Episode:
    title: str
    place: str  # village, cimetiere, foret, eglise, manoir
    text: str
    choices: tuple[Choice, ...] = field(default_factory=tuple)


SEASON_TITLE = "Les Disparus de Brumeval"

EPISODES = [
    Episode(
        "La lanterne éteinte", "village",
        "C'est la fête des lanternes à Brumeval. À minuit, un cri traverse la place : **{victim}** a disparu. "
        "On ne retrouve que sa lanterne, encore tiède, posée au bord du chemin du vieux cimetière. "
        "**{hero}** ramasse la lanterne… et remarque que **{suspect}** s'éloigne très vite dans la brume.",
        (Choice("Suivre les traces vers le cimetière", "tomb", "courage",
                "Le village a suivi les traces dans la boue : elles s'arrêtent net devant une **tombe sans nom**."),
         Choice("Interroger {suspect}", "eye", "soupcon",
                "{suspect} jure qu'il n'a rien vu… mais ses mains tremblent, et il refuse de dire où il allait."),
         Choice("Allumer toutes les lanternes du village", "candle", "lumiere",
                "Toutes les lanternes ont brillé jusqu'à l'aube : cette nuit, aucune ombre n'a osé approcher.")),
    ),
    Episode(
        "La tombe sans nom", "cimetiere",
        "Au petit matin, **{hero}** trouve une lettre glissée sous sa porte, scellée de cire orange : "
        "« *Ce qui a été pris sera rendu le 31… si le village paie le prix.* » La lettre est signée d'un simple **R**. "
        "Au cimetière, la tombe sans nom a été creusée de l'intérieur.",
        (Choice("Descendre dans la tombe", "skull", "courage",
                "Sous la tombe, un tunnel étroit file vers l'église. Quelqu'un l'a emprunté il y a peu : la terre est fraîche."),
         Choice("Montrer la lettre à Morgane la sorcière", "witch", "savoir",
                "Morgane a reniflé la cire : « De la citrouille brûlée… Ce **R** n'est pas humain. »"),
         Choice("Brûler la lettre au milieu de la place", "fire", "lumiere",
                "La lettre s'est consumée en flammes vertes. Au même instant, toutes les citrouilles du village ont grimacé.")),
    ),
    Episode(
        "Le grimoire de Morgane", "foret",
        "Dans sa cabane au fond de la forêt, Morgane ouvre un grimoire couvert de toiles d'araignée. "
        "« Tous les cent ans, un esprit réclame une âme à Brumeval. La dernière fois, il a pris un enfant. "
        "Cette fois, il a pris **{victim}**. » **{suspect}** apparaît alors à la fenêtre, essoufflé, couvert de terre.",
        (Choice("Laisser entrer {suspect} et l'écouter", "door", "savoir",
                "{suspect} a tout raconté : chaque nuit, il entend une voix qui l'appelle depuis l'église."),
         Choice("Attacher {suspect} jusqu'au matin", "web", "soupcon",
                "{suspect} a passé la nuit attaché. Au matin, les cordes étaient coupées… de l'intérieur."),
         Choice("Lire la formule de protection du grimoire", "book", "lumiere",
                "La formule a fait trembler la forêt : un cercle de champignons lumineux entoure désormais le village.")),
    ),
    Episode(
        "Le bal des masques", "manoir",
        "Le maire organise un bal masqué au manoir pour « rassurer le village ». Tout le monde danse, sauf **{hero}**, "
        "qui remarque qu'un invité porte un masque de citrouille… et ne laisse aucun reflet dans les miroirs. "
        "Sur sa cape, une broderie : un **R** orange.",
        (Choice("Arracher le masque devant tout le monde", "pumpkin_angry", "courage",
                "Sous le masque… il n'y avait rien. Juste du vent glacé, et un rire qui a fait éclater les vitres."),
         Choice("Le suivre discrètement", "ghost", "savoir",
                "L'invité masqué est sorti par la cave. Il parlait à quelqu'un : « Encore trois nuits, et l'âme sera à moi. »"),
         Choice("Accuser {suspect}, qui portait le même masque", "eye", "soupcon",
                "Le village s'est retourné contre {suspect}. Pendant la dispute, l'invité masqué a tranquillement disparu.")),
    ),
    Episode(
        "La cloche de minuit", "eglise",
        "Cette nuit, la cloche de l'église sonne treize coups. Les villageois s'enferment chez eux. "
        "**{hero}** distingue une silhouette au sommet du clocher : c'est **{victim}**, immobile, les yeux "
        "brillants comme deux braises. Sa voix descend jusqu'à la place : « *Ne venez pas me chercher…* »",
        (Choice("Monter au clocher", "bat", "courage",
                "En haut du clocher, il ne restait que l'écharpe de {victim}, et des empreintes de racines brûlées."),
         Choice("Faire sonner la cloche à l'envers", "crystal", "savoir",
                "La cloche sonnée à l'envers a rompu un sortilège : on a entendu {victim} crier « LA CRYPTE ! »"),
         Choice("Encercler l'église de bougies", "candle", "lumiere",
                "Cent bougies ont encerclé l'église. La silhouette a reculé dans l'ombre, comme brûlée par la lumière.")),
    ),
    Episode(
        "La crypte sous l'église", "eglise",
        "Sous les dalles de l'église, un escalier descend vers une crypte oubliée. Des dizaines de citrouilles y "
        "sont alignées, chacune portant un nom gravé : les disparus des siècles passés. La dernière porte "
        "le nom de **{victim}**… et l'avant-dernière, celui de **{suspect}**.",
        (Choice("Briser la citrouille de {victim}", "pumpkin_lit", "courage",
                "La citrouille a éclaté : une lumière dorée s'en est échappée et a filé vers la forêt. Une âme libérée ?"),
         Choice("Déchiffrer les gravures des murs", "scroll", "savoir",
                "Les gravures racontent l'histoire du **Roi Citrouille** : il ne peut être vaincu que par un nom crié trois fois."),
         Choice("Condamner la crypte et prévenir le village", "lock", "soupcon",
                "La crypte est scellée… mais le village est terrifié, et beaucoup pensent maintenant que {suspect} est complice.")),
    ),
    Episode(
        "Le visage du Roi", "foret",
        "La veille d'Halloween, la forêt s'embrase de lueurs orange. Au centre d'une clairière se dresse le "
        "**Roi Citrouille**, couronné de ronces, tenant **{victim}** endormi dans ses racines. « *Demain soir, "
        "l'âme sera mienne… à moins qu'un autre ne prenne sa place.* » Tous les regards se tournent vers **{suspect}**.",
        (Choice("{hero} se propose à la place de {victim}", "heart", "courage",
                "{hero} s'est avancé. Le Roi a souri : « Un cœur courageux… le marché est presque honnête. »"),
         Choice("Crier trois fois le vrai nom du Roi", "lightning", "savoir",
                "Au troisième cri, le Roi s'est fissuré comme une vieille écorce. Il hurle, mais il est affaibli."),
         Choice("Livrer {suspect} au Roi", "skull", "soupcon",
                "Le village a poussé {suspect} vers la clairière. Le Roi a éclaté de rire : « Mauvais choix… »")),
    ),
    Episode("Halloween : le dénouement", "village", "", ()),
]

ENDINGS = {
    "courage": ("Le sacrifice du héros",
                "**{hero}** affronte le Roi Citrouille seul, une lanterne à la main. Au dernier coup de minuit, la lanterne "
                "explose de lumière : le Roi est pulvérisé en mille graines brûlantes. **{victim}** se réveille dans la "
                "clairière, et **{hero}** devient la légende de Brumeval. **Fin héroïque.**"),
    "lumiere": ("La nuit des mille lanternes",
                "Tout le village allume ses lanternes en même temps. La lumière est si forte que le Roi Citrouille ne peut "
                "plus se cacher dans l'ombre : il se dessèche et tombe en poussière. **{victim}** rentre à la maison "
                "sous les applaudissements. **Fin lumineuse.**"),
    "savoir": ("Le nom véritable",
               "Grâce au grimoire de Morgane, le village connaît le vrai nom du Roi. Crié trois fois par tout Brumeval, "
               "il brise la malédiction pour toujours : toutes les âmes de la crypte sont libérées, et **{victim}** avec "
               "elles. **Fin parfaite.**"),
    "soupcon": ("Le mauvais coupable",
                "Le village était si occupé à soupçonner **{suspect}** qu'il n'a pas vu le vrai danger. À minuit, le Roi "
                "Citrouille emporte **{victim}**… et **{suspect}**, innocent depuis le début, disparaît avec. Dans un an, "
                "le Roi reviendra. **Fin maudite.**"),
}


def ending(totals: dict[str, int]) -> str:
    """The leaning with the most votes; ties are broken in LEANINGS order (courage first)."""
    return max(LEANINGS, key=lambda k: (totals.get(k, 0), -LEANINGS.index(k)))


def fill(text: str, cast: dict[str, str]) -> str:
    return text.format(**cast)
