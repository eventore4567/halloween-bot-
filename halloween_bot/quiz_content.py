"""Halloween quiz question bank and horror-film screenshots.

Classic horror-film stills are linked to Wikimedia Commons file pages with
public-domain descriptions. Do not use poster pictures with visible film titles.
Film guessing is a casual candy game: never scores the real-prize tournament.
"""
from __future__ import annotations

import random
from urllib.parse import quote

DIFFICULTIES = {
    "facile":   {"time": 45, "candies": 65,  "label": "🟢 Facile"},
    "moyen":    {"time": 40, "candies": 115, "label": "🟡 Moyen"},
    "difficile":{"time": 35, "candies": 180, "label": "🔴 Difficile"},
    "expert":   {"time": 30, "candies": 270, "label": "💀 Expert"},
}
# Question | correct answer | three plausible alternatives.
QUESTIONS = {
 "halloween": {
  "facile": [
   ("Quand célèbre-t-on Halloween ?", "31 octobre", "1er janvier", "14 février", "25 décembre"),
   ("Quel objet sculpte-t-on pour Halloween ?", "Citrouille", "Pomme", "Châtaigne", "Pastèque"),
   ("Quel animal accompagne traditionnellement les sorcières ?", "Chat noir", "Panda", "Dauphin", "Cheval blanc"),
   ("Quel fruit célèbre un jeu d'Halloween dans l'eau ?", "Pomme", "Citron", "Banane", "Melon"),
   ("Comment dit-on « fantôme » en anglais ?", "Ghost", "Witch", "Pumpkin", "Skeleton"),
   ("Quel est le cri anglais pour effrayer quelqu'un ?", "Boo!", "Moo!", "Hey!", "Go!"),
   ("Quel personnage est souvent enveloppé de bandelettes ?", "Momie", "Vampire", "Troll", "Sorcière"),
   ("Quel symbole sert souvent à éclairer Halloween ?", "Citrouille-lanterne", "Étoile de mer", "Parapluie", "Nuage"),
  ],
  "moyen": [
   ("Comment appelle-t-on la citrouille-lanterne en anglais ?", "Jack-o'-lantern", "Ghost light", "Pumpkin Moon", "Orange Witch"),
   ("Quel pays est souvent lié aux origines de Samain ?", "Irlande", "Japon", "Égypte", "Mexique"),
   ("Quel esprit était représenté par une lanterne en navet ?", "Jack", "Morgan", "Abel", "Thomas"),
   ("Quel ancien festival celtique a influencé Halloween ?", "Samhain", "Lupercales", "Beltane d'été", "Saturnales"),
   ("Lequel de ces objets est le plus souvent associé à une sorcière ?", "Chaudron", "Trident", "Harpe", "Canon"),
   ("Quel insecte file les toiles que l'on utilise en décoration ?", "Araignée", "Abeille", "Fourmi", "Mouche"),
   ("Dans quel mois se trouve la Toussaint ?", "Novembre", "Mars", "Juillet", "Janvier"),
   ("Quelle créature est associée à la pleine lune ?", "Loup-garou", "Momie", "Squelette", "Gobelin"),
  ],
  "difficile": [
   ("Que signifie « Samhain » dans les sources irlandaises ?", "Nom d'une fête de fin de saison", "Nom d'un château", "Épée sacrée", "Nom d'une reine"),
   ("Quelle racine était traditionnellement sculptée dans certaines régions ?", "Navet", "Gingembre", "Radis noir", "Patate douce"),
   ("Quelle civilisation a transmis une grande partie du folklore de Samhain ?", "Celtes", "Incas", "Mongols", "Phéniciens"),
   ("Quel nom porte le lendemain d'Halloween dans le calendrier chrétien ?", "Toussaint", "Pentecôte", "Épiphanie", "Ascension"),
   ("Que désigne le terme anglais « trick-or-treat » ?", "Des friandises ou une farce", "Un jeu de dés", "Une danse", "Une histoire"),
   ("Quel symbole folklorique est un présage dans certains récits ?", "Corbeau", "Coccinelle", "Dauphin", "Hirondelle"),
  ],
  "expert": [
   ("Dans la tradition irlandaise, Samhain marquait surtout...", "Le début de l'hiver", "Le solstice d'été", "L'équinoxe de printemps", "Une éclipse"),
   ("Le titre « Dracula » s'inspire de quel personnage historique ?", "Vlad III", "Richard Ier", "Ivan IV", "Charlemagne"),
   ("Quel auteur a popularisé « La Légende de Sleepy Hollow » ?", "Washington Irving", "Edgar Allan Poe", "H. P. Lovecraft", "Bram Stoker"),
   ("Dans quel roman apparaît le cavalier sans tête de Sleepy Hollow ?", "Dans une nouvelle de Washington Irving", "Dans Frankenstein", "Dans Dracula", "Dans Le Portrait de Dorian Gray"),
  ],
 },
 "horreur": {
  "facile": [
   ("Quel personnage porte habituellement des crocs ?", "Vampire", "Momie", "Zombie", "Fantôme"),
   ("Quel objet traditionnel effraie les vampires dans les légendes ?", "Ail", "Citrouille", "Chocolat", "Parapluie"),
   ("Quel monstre se transforme sous la pleine lune ?", "Loup-garou", "Zombie", "Golem", "Momie"),
   ("Dans quel lieu les fantômes sont-ils souvent représentés ?", "Maison hantée", "Aquarium", "Boulangerie", "Bibliothèque"),
   ("Quel son est associé à un château hanté ?", "Grincement de porte", "Klaxon de vélo", "Jingle publicitaire", "Sonnette d'école"),
  ],
  "moyen": [
   ("Qui a écrit le roman « Dracula » ?", "Bram Stoker", "Mary Shelley", "Stephen King", "Victor Hugo"),
   ("Quelle autrice a écrit « Frankenstein » ?", "Mary Shelley", "Agatha Christie", "George Sand", "Jane Austen"),
   ("Quelle créature est au centre du film « Nosferatu » (1922) ?", "Vampire", "Loup-garou", "Momie", "Robot"),
   ("Quel auteur est célèbre pour ses contes macabres et « Le Corbeau » ?", "Edgar Allan Poe", "Jules Verne", "Molière", "Émile Zola"),
   ("Que signifie « found footage » au cinéma ?", "Images présentées comme retrouvées", "Film muet", "Scène musicale", "Film en dessin animé"),
  ],
  "difficile": [
   ("Qui a réalisé « La Nuit des morts-vivants » (1968) ?", "George A. Romero", "John Carpenter", "James Wan", "Wes Craven"),
   ("Qui a réalisé « Nosferatu » (1922) ?", "F. W. Murnau", "Fritz Lang", "Alfred Hitchcock", "Luis Buñuel"),
   ("Dans quel film apparaît le personnage du Dr. Caligari ?", "Le Cabinet du docteur Caligari", "Le Golem", "Metropolis", "Vampyr"),
   ("Quelle décennie a vu sortir le film « Psychose » ?", "Années 1960", "Années 1980", "Années 2000", "Années 1940"),
   ("Quel compositeur a signé la musique de « Halloween » (1978) ?", "John Carpenter", "Danny Elfman", "Ennio Morricone", "Hans Zimmer"),
  ],
  "expert": [
   ("Quel artiste a créé le monstre littéraire « Cthulhu » ?", "H. P. Lovecraft", "Bram Stoker", "Arthur Conan Doyle", "Charles Dickens"),
   ("Le « cinéma expressionniste » est surtout associé à...", "L'Allemagne des années 1920", "L'Italie des années 1990", "Le Japon des années 2010", "Hollywood des années 1970"),
   ("Quel est le titre original allemand du film « Nosferatu » (1922) ?", "Nosferatu – Eine Symphonie des Grauens", "Das Vampirreich", "Dracula: Die Nacht", "Die Unsterblichen"),
   ("Quelle innovation narrative caractérise « Le Cabinet du docteur Caligari » ?", "Un récit-cadre au narrateur peu fiable", "Une narration à la première personne en temps réel", "Un plan-séquence de trois heures", "Un documentaire animalier"),
  ],
 },
 "science": {
  "facile": [
   ("Quel astre éclaire souvent les scènes de nuit ?", "La Lune", "Mars", "Jupiter", "Le Soleil"),
   ("Combien de pattes possède une araignée ?", "8", "6", "10", "12"),
   ("Quel organe pompe le sang ?", "Le cœur", "Le poumon", "Le rein", "Le foie"),
   ("Comment appelle-t-on la peur intense des araignées ?", "Arachnophobie", "Acrophobie", "Claustrophobie", "Agoraphobie"),
  ],
  "moyen": [
   ("Quel groupe d'animaux comprend les chauves-souris ?", "Mammifères", "Oiseaux", "Reptiles", "Amphibiens"),
   ("Quelle substance donne sa couleur orange à la citrouille ?", "Caroténoïdes", "Hémoglobine", "Chlorophylle", "Mélanine"),
   ("De quoi les araignées utilisent-elles la soie ?", "De protéines", "De verre", "De cellulose pure", "De métal"),
   ("Pourquoi voit-on parfois de la brume près du sol ?", "Condensation de vapeur d'eau", "Cendre d'étoiles", "Lumière solide", "Champ magnétique"),
  ],
  "difficile": [
   ("Quelle méduse est connue pour pouvoir revenir à un stade immature ?", "Turritopsis dohrnii", "Aurelia aurita", "Physalia physalis", "Cyanea capillata"),
   ("Quel processus permet à certains organismes d'émettre de la lumière ?", "Bioluminescence", "Photosynthèse", "Sublimation", "Évaporation"),
   ("Quel pigment participe à la couleur noire du pelage d'un chat ?", "Eumélanine", "Bilirubine", "Kératine", "Mélatonine"),
   ("Comment se nomme le vol des chauves-souris en utilisant les échos ?", "Écholocalisation", "Photosensibilité", "Hydrolocation", "Magnétisme"),
  ],
  "expert": [
   ("Quel ordre taxonomique comprend les chauves-souris ?", "Chiroptera", "Rodentia", "Carnivora", "Primates"),
   ("Quel nom porte le retour cellulaire observé chez Turritopsis ?", "Transdifférenciation", "Osmose", "Fermentation", "Méiose"),
   ("Quelle molécule est le principal constituant des fils de soie d'araignée ?", "Spidroïne", "Insuline", "Hémoglobine", "Actine seule"),
   ("Chez les champignons bioluminescents, quelle enzyme participe à la réaction ?", "Luciférase", "Amylase", "Lipase", "Catalase"),
  ],
 },
 "culture": {
  "facile": [
   ("Qui a écrit « Harry Potter » ?", "J. K. Rowling", "Tolkien", "Victor Hugo", "Jules Verne"),
   ("Quel est le plus grand océan ?", "Pacifique", "Indien", "Atlantique", "Arctique"),
   ("Quelle planète est surnommée la planète rouge ?", "Mars", "Vénus", "Jupiter", "Saturne"),
   ("Dans quel pays se trouve la tour Eiffel ?", "France", "Belgique", "Italie", "Maroc"),
  ],
  "moyen": [
   ("Quel peintre a réalisé « La Nuit étoilée » ?", "Vincent van Gogh", "Monet", "Picasso", "Dalí"),
   ("Qui a écrit « L'Étrange Cas du docteur Jekyll et de M. Hyde » ?", "Robert Louis Stevenson", "Bram Stoker", "Mary Shelley", "H. G. Wells"),
   ("Quel est le symbole chimique du fer ?", "Fe", "F", "Ir", "Fr"),
   ("En quel siècle a commencé la Première Guerre mondiale ?", "XXe siècle", "XIXe siècle", "XVIIIe siècle", "XXIe siècle"),
  ],
  "difficile": [
   ("Quel auteur a créé le détective Auguste Dupin ?", "Edgar Allan Poe", "Agatha Christie", "Conan Doyle", "Georges Simenon"),
   ("Quel scientifique a proposé le modèle héliocentrique au XVIe siècle ?", "Nicolas Copernic", "Galilée", "Newton", "Einstein"),
   ("Quelle langue parlait-on principalement dans la Rome antique ?", "Latin", "Grec moderne", "Allemand", "Espagnol"),
   ("Quel est le nom de la plus grande lune de Saturne ?", "Titan", "Io", "Europe", "Callisto"),
  ],
  "expert": [
   ("Quel auteur a écrit le récit « La Chute de la maison Usher » ?", "Edgar Allan Poe", "Bram Stoker", "Arthur Machen", "Lovecraft"),
   ("En quelle année fut publiée la première édition de « Frankenstein » ?", "1818", "1847", "1897", "1791"),
   ("Quel philosophe est l'auteur du « Discours de la méthode » ?", "René Descartes", "Blaise Pascal", "Voltaire", "Auguste Comte"),
   ("Quel élément porte le numéro atomique 74 ?", "Tungstène", "Osmium", "Hafnium", "Rhénium"),
  ],
 },
}

# Source pages were checked manually on Wikimedia Commons, most US public-domain
# stills. Movie images are *not* competitive point challenges because they can be
# reverse-image-searched. Preserve source attribution and review rights by locale.
FILMS = [
    {"name":"Nosferatu", "aliases":["Nosferatu le vampire", "Nosferatu 1922"],
     "difficulty":"moyen", "year":1922, "hint":"Un vampire allemand du cinéma muet",
     "file":"Nosferatu.jpg"},
    {"name":"Le Cabinet du docteur Caligari", "aliases":["The Cabinet of Dr. Caligari", "Das Cabinet des Dr Caligari"],
     "difficulty":"difficile", "year":1920, "hint":"Un cauchemar expressionniste allemand",
     "file":"CABINETOFDRCALIGARI-05.jpg"},
    {"name":"Le Fantôme de l'Opéra", "aliases":["The Phantom of the Opera"],
     "difficulty":"difficile", "year":1925, "hint":"Un masque, une scène et un opéra",
     "file":"The Phantom of the Opera (1925) still.jpg"},
    {"name":"La Nuit des morts-vivants", "aliases":["Night of the Living Dead"],
     "difficulty":"facile", "year":1968, "hint":"Un classique de zombies",
     "file":"Zombies NightoftheLivingDead.jpg"},
    {"name":"Dracula", "aliases":["Dracula 1931"],
     "difficulty":"facile", "year":1931, "hint":"Un célèbre vampire de cinéma",
     "file":"Dracula1931BelaLugosiColor.png"},
    {"name":"La Nuit de tous les mystères", "aliases":["House on Haunted Hill"],
     "difficulty":"moyen", "year":1959, "hint":"Une maison, un groupe d'invités, des mystères",
     "file":"Alan Marshal.png"},
]
for film in FILMS:
    film["source"] = "https://commons.wikimedia.org/wiki/File:" + quote(film["file"].replace(" ", "_"))
    film["image"] = (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        + quote(film["file"].replace(" ", "_"))
        + "?width=800"
    )


def generate_question(category="halloween", difficulty="facile"):
    if category not in QUESTIONS or difficulty not in DIFFICULTIES:
        raise ValueError("Unknown quiz configuration")
    pool = QUESTIONS[category].get(difficulty) or QUESTIONS[category]["facile"]
    text, correct, wrong_1, wrong_2, wrong_3 = random.choice(pool)
    choices = [correct, wrong_1, wrong_2, wrong_3]
    random.shuffle(choices)
    return {
        "question": text,
        "answers": choices,
        "correct": choices.index(correct),
        "difficulty": difficulty,
        "category": category,
        "time": DIFFICULTIES[difficulty]["time"],
        "reward": DIFFICULTIES[difficulty]["candies"],
    }


def generate_film(difficulty="facile"):
    if difficulty not in DIFFICULTIES:
        raise ValueError("Invalid difficulty")
    pool = [f for f in FILMS if f["difficulty"] == difficulty]
    if not pool:
        # Expert is intentionally not offered: too few licensed film stills.
        raise ValueError("No film in this difficulty")
    film = random.choice(pool)
    distractors = [f["name"] for f in FILMS if f["name"] != film["name"]]
    choices = random.sample(distractors, 3) + [film["name"]]
    random.shuffle(choices)
    data = {
        "question": "Quel est le titre de ce film d'horreur ?",
        "answers": choices,
        "correct": choices.index(film["name"]),
        "difficulty": difficulty,
        "category": "cinema",
        "time": DIFFICULTIES[difficulty]["time"] + 10,
        "reward": DIFFICULTIES[difficulty]["candies"] + 40,
        "image": film["image"],
        "source": film["source"],
        "year": film["year"],
        "hint": film["hint"],
    }
    return data
