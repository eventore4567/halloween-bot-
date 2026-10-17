-- BloxHub / races : fiches des races et de leurs évolutions.
-- Données vérifiées le 17/10/2026 à partir de guides publics. Remarque : les races ont été
-- renommées dans le jeu (Skypiea → Angel, Fishman → Shark, Mink → Rabbit).

return function(Hub)
	local UI = Hub.Modules.ui
	local Req = Hub.Modules.requirements
	local Info = Hub.Modules.player_info
	local c = UI.c

	local V2_STEPS = {
		"Niveau 850 et quête du Colisée terminée (Bartilo, Café du Kingdom of Rose).",
		"Parle à l'Alchimiste dans la Green Zone (Second Sea) pour lancer la quête.",
		"Récupère les 3 fleurs sur le même serveur : bleue (la nuit), rouge (le jour), jaune (drop aléatoire sur les ennemis, ex. Swan Pirates).",
		"Rapporte-les à l'Alchimiste. Attention : les fleurs sont perdues si tu meurs ou quittes le serveur.",
	}

	local function v3Steps(trial)
		return {
			"Race en V2 et Don Swan vaincu.",
			"Parle à Arowe (Second Sea) pour lancer la quête de ta race.",
			"Épreuve : " .. trial,
			"Retourne voir Arowe avec 2 000 000 Beli sur toi : ils sont prélevés à la validation.",
		}
	end

	local V3_BASE = {
		{ kind = "sea", value = 2 },
		{ kind = "raceVersion", value = 2 },
		{ kind = "manual", label = "Don Swan vaincu" },
		{ kind = "beli", value = 2000000 },
	}

	local function concat(...)
		local out = {}
		for _, list in ipairs({ ... }) do
			for _, v in ipairs(list) do
				table.insert(out, v)
			end
		end
		return out
	end

	local REROLL = "Tort (Café du Kingdom of Rose, Second Sea) change ta race au hasard pour 3 000 Fragments parmi Human, Shark, Angel et Rabbit (Mink)."

	local RACES = {
		{
			id = "angel_v2",
			name = "Angel V2",
			icon = "🪽",
			sea = 2,
			summary = "Première évolution de la race Angel (Skypiea).",
			reqs = {
				{ kind = "race", value = "Angel" },
				{ kind = "sea", value = 2 },
				{ kind = "level", value = 850 },
				{ kind = "manual", label = "Quête du Colisée terminée" },
			},
			steps = V2_STEPS,
		},
		{
			id = "angel_v3",
			name = "Angel V3",
			icon = "🪽",
			sea = 2,
			summary = "Évolution via Arowe.",
			reqs = concat({ { kind = "race", value = "Angel" } }, V3_BASE),
			steps = v3Steps("vaincre un autre joueur de race Angel."),
		},
		{
			id = "angel_v4",
			name = "Angel V4",
			icon = "🌕",
			sea = 3,
			summary = "Éveil de race (Race Awakening) au Temple of Time, Third Sea.",
			reqs = {
				{ kind = "race", value = "Angel" },
				{ kind = "sea", value = 3 },
				{ kind = "raceVersion", value = 3 },
				{ kind = "manual", label = "rip_indra vaincu" },
				{ kind = "own", names = { "Mirror Fractal" }, label = "Mirror Fractal (Dough King)" },
			},
			steps = {
				"Obtiens le Mirror Fractal sur le Dough King.",
				"Au sommet du Great Tree, interagis avec la Mysterious Force pour accéder au Temple of Time.",
				"Sur Mirage Island, la nuit, monte au point le plus haut et active ta capacité V3 vers la lune.",
				"Après le message de résonance, trouve la Blue Gear sur Mirage Island (temps limité).",
				"Au Temple of Time, active le levier caché puis passe l'épreuve de ta race (en groupe, avec d'autres races en V3+).",
			},
			warning = "⚠ Les guides divergent sur la pleine lune (encore requise ou seulement la nuit) et sur le nombre d'épreuves. Vérifie en jeu.",
		},
		{
			id = "human",
			name = "Human",
			icon = "🧍",
			sea = 2,
			summary = "Race de départ possible. " .. REROLL,
			reqs = concat({ { kind = "race", value = "Human" } }, V3_BASE),
			steps = concat(
				{ "V1 : race de départ aléatoire ou reroll chez Tort (3 000 Fragments, aléatoire)." },
				{ "V2 : quête de l'Alchimiste (voir Angel V2, mêmes étapes)." },
				{ "V3 : épreuve d'Arowe : vaincre Diamond, Jeremy et Fajita (ordre libre), puis payer 2 000 000 Beli." }
			),
		},
		{
			id = "shark",
			name = "Shark",
			icon = "🦈",
			sea = 2,
			summary = "Anciennement Fishman. " .. REROLL,
			reqs = concat({ { kind = "race", value = "Shark" } }, V3_BASE),
			steps = {
				"V1 : race de départ aléatoire ou reroll chez Tort (3 000 Fragments, aléatoire).",
				"V2 : quête de l'Alchimiste (voir Angel V2, mêmes étapes).",
				"V3 : épreuve d'Arowe : vaincre un Sea Beast apparu naturellement (ceux invoqués ne comptent pas), puis payer 2 000 000 Beli.",
			},
		},
		{
			id = "mink",
			name = "Mink (Rabbit)",
			icon = "🐇",
			sea = 2,
			summary = "Renommée Rabbit dans le jeu. " .. REROLL,
			reqs = concat({ { kind = "race", value = "Mink" } }, V3_BASE),
			steps = {
				"V1 : race de départ aléatoire ou reroll chez Tort (3 000 Fragments, aléatoire).",
				"V2 : quête de l'Alchimiste (voir Angel V2, mêmes étapes).",
				"V3 : épreuve d'Arowe : ouvrir 30 coffres, puis payer 2 000 000 Beli.",
			},
		},
		{
			id = "cyborg",
			name = "Cyborg",
			icon = "🤖",
			sea = 2,
			summary = "Race obtenue par le puzzle du Secret Laboratory (Second Sea).",
			reqs = {
				{ kind = "sea", value = 2 },
				{ kind = "own", names = { "Fist of Darkness" }, label = "Fist of Darkness (Sea Beasts de la Second Sea ≈5 %, ou coffres)" },
				{ kind = "own", names = { "Core Brain" }, label = "Core Brain (drop rare du raid Order)" },
				{ kind = "fragments", value = 3500, label = "3 500 Fragments (Microchip 1 000 + race 2 500)" },
			},
			steps = {
				"Place le Fist of Darkness dans la machine du Secret Laboratory.",
				"Achète une Microchip à Arithmetic (salle secrète au-dessus du bâtiment du Smoke Admiral) : 1 000 Fragments.",
				"Lance le raid Order et obtiens le Core Brain (drop rare).",
				"Place le Core Brain dans la machine : l'escalier secret s'ouvre, achète Cyborg pour 2 500 Fragments.",
				"V3 : épreuve d'Arowe : montrer un fruit physique (il ne le prend pas), puis payer 2 000 000 Beli.",
			},
			warning = "⚠ Le taux de drop du Core Brain varie selon les guides (2,5 % à 5 %).",
		},
		{
			id = "ghoul",
			name = "Ghoul",
			icon = "🧛",
			sea = 2,
			summary = "Race obtenue auprès d'Experimic, dans la cuisine du Cursed Ship.",
			reqs = {
				{ kind = "sea", value = 2 },
				{ kind = "level", value = 1000 },
				{ kind = "material", name = "Ectoplasm", value = 100 },
				{ kind = "own", names = { "Hellfire Torch" }, label = "Hellfire Torch (Cursed Captain)" },
			},
			steps = {
				"Farme 100 Ectoplasm sur les ennemis du Cursed Ship (ex. Ship Stewards en cuisine).",
				"Obtiens la Hellfire Torch sur le Cursed Captain (niv. 1325) ; le taux varie selon les guides.",
				"Parle à Experimic (cuisine du Cursed Ship) et choisis l'échange.",
				"V3 : épreuve d'Arowe : vaincre 5 joueurs sans mourir, puis payer 2 000 000 Beli.",
			},
			warning = "⚠ Taux de drop de la Hellfire Torch et épreuve V3 Ghoul : informations variables selon les guides.",
		},
	}

	local Races = { cards = {}, RACES = RACES }

	local function refreshBadges()
		local ctx = Info:context()
		for _, entry in ipairs(RACES) do
			local card = Races.cards[entry.id]
			if card then
				local sum = Req.summarize(entry.reqs, ctx)
				card.setBadge(("%d %%"):format(math.floor(sum.ratio * 100 + 0.5)))
				if card.open then
					card.rebuild()
				end
			end
		end
	end
	Races.refresh = refreshBadges

	local page = UI:addPage("races", {
		title = "Races",
		subtitle = "Obtention et évolutions V2 / V3 / V4",
		icon = "🧬",
		order = 4,
		onShow = refreshBadges,
	})
	local root = page.frame

	local infoCard = c.card(root)
	local raceLabel = c.label(infoCard, "", { bold = true })
	c.label(infoCard, "La version (V2, V3, V4) n'est pas toujours lisible par script : les points « ? » sont à confirmer en jeu.", { muted = true, size = 12 })

	local function updateRaceLabel()
		local s = Info:snapshot()
		raceLabel.Text = "Ta race : " .. (s.race or "non détectée") .. (s.raceVersion and (" V" .. s.raceVersion) or "")
	end
	updateRaceLabel()

	c.section(root, "Races")
	for _, entry in ipairs(RACES) do
		local card = c.collapsible(root, entry.name, (Info.SEA_NAMES[entry.sea] or "") .. "  ·  " .. (entry.summary or ""), function(body)
			Req.render(body, entry, Info:context())
		end, { icon = entry.icon, badge = "—" })
		Races.cards[entry.id] = card
		UI:addSearch(entry.name, "race v2 v3 v4 " .. (entry.summary or ""), "races", card.frame)
	end

	c.label(root, "✓ vérifié  ·  ✗ manquant  ·  ? non vérifiable par script (à confirmer en jeu).", { muted = true, size = 11 })
	c.label(root, "Sources : guides publics vérifiés le 17/10/2026. Le jeu évolue : en cas de doute, vérifie en jeu.", { muted = true, size = 11 })

	local baseShow = page.onShow
	page.onShow = function()
		updateRaceLabel()
		baseShow()
	end

	return Races
end
