-- BloxHub / automation : page d'état des fonctions d'automatisation.
-- BloxHub ne contrôle pas le personnage. Cette page dit clairement ce qui existe,
-- ce qui n'existe pas, et quels risques comporte l'utilisation d'un exécuteur.

return function(Hub)
	local UI = Hub.Modules.ui
	local c = UI.c

	local NOT_INCLUDED = {
		{ "Auto Farm", "déplacer le personnage et attaquer les ennemis à ta place" },
		{ "Auto Boss", "chercher et combattre les boss à ta place" },
		{ "Auto Sword", "enchaîner les puzzles et combats des épées à ta place" },
		{ "Auto Mastery", "utiliser les attaques en boucle pour monter la maîtrise" },
		{ "Auto Quest", "prendre et rendre les quêtes à ta place" },
	}

	local PRESENT = {
		{ "Dashboard", "niveau, Sea, race, Beli, Fragments, fruit, arme et maîtrise" },
		{ "Progression", "objectifs selon ton niveau, déblocages, maîtrises, boss, guide des Seas" },
		{ "Équipements", "Pole V1/V2, Saber, Rengoku, CDK, Godhuman, Skull Guitar : prérequis et ressources manquantes" },
		{ "Races", "suivi Angel V2 / V3 / V4, Human, Shark, Mink, Cyborg, Ghoul" },
		{ "Inventaire", "lecture à la demande des matériaux (lecture seule)" },
		{ "Diagnostic", "compatibilité de l'exécuteur, tâches, journal des erreurs" },
	}

	local page = UI:addPage("automation", {
		title = "Automatisation",
		subtitle = "Ce qui est inclus, ce qui ne l'est pas, et les risques",
		icon = "🤖",
		order = 60,
	})
	local root = page.frame

	c.section(root, "Non inclus dans BloxHub")
	local missing = c.card(root, { gap = 6 })
	for _, f in ipairs(NOT_INCLUDED) do
		c.status(missing, "missing", f[1], "non développé — " .. f[2])
	end
	c.label(missing, "BloxHub ne contrôle jamais ton personnage. Ces fonctions jouent à ta place : c'est de la triche selon les règles de Roblox et de Blox Fruits, et elles pèsent sur les autres joueurs (boss et drops partagés sur le serveur). Elles ne sont pas fournies et aucun bouton ne fait semblant de les activer.", { muted = true, size = 12 })
	UI:addSearch("Auto Farm, Auto Boss, Auto Sword, Auto Mastery, Auto Quest", "automatisation auto farm boss sword mastery quest", "automation", missing)

	c.section(root, "Inclus (suivi, lecture seule)")
	local present = c.card(root, { gap = 6 })
	for _, f in ipairs(PRESENT) do
		c.status(present, "ok", f[1], f[2])
	end

	c.section(root, "Risques")
	local risks = c.card(root, { gap = 6 })
	c.status(risks, "warn", "Exécuteur", "lancer un script avec un exécuteur (Opiumware compris) enfreint les conditions d'utilisation de Roblox, même pour un hub en lecture seule.")
	c.status(risks, "warn", "Détection", "Roblox et Blox Fruits ont des systèmes de détection. Aucun script n'est indétectable et BloxHub n'essaie pas de se cacher.")
	c.status(risks, "warn", "Sanctions possibles", "avertissement, bannissement temporaire ou définitif du compte.")
	c.status(risks, "warn", "Lecture d'inventaire", "envoie une requête au serveur du jeu (lecture seule, 1 fois / 15 s max). Désactivable dans Paramètres → Modules.")
	c.label(risks, "Pour ne rien risquer sur ton compte principal, utilise un compte secondaire.", { muted = true, size = 12 })
	UI:addSearch("Risques et détection", "ban bannissement anti triche detection risque", "automation", risks)

	return {}
end
