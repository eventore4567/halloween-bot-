-- BloxHub / equipment : fiches des équipements (prérequis, étapes, progression, ressources).
-- Données vérifiées le 17/10/2026 à partir de guides publics. Les divergences entre
-- sources sont signalées par un avertissement plutôt que tranchées arbitrairement.

return function(Hub)
	local UI = Hub.Modules.ui
	local Req = Hub.Modules.requirements
	local Info = Hub.Modules.player_info
	local c = UI.c

	local ITEMS = {
		{
			id = "pole_v1",
			name = "Pole (1st Form)",
			tag = "Pole V1",
			icon = "⚡",
			sea = 1,
			summary = "Épée lâchée par le boss Thunder God dans l'Upper Skylands (First Sea).",
			owned = { "Pole (1st Form)" },
			reqs = {
				{ kind = "level", value = 575, label = "Niveau conseillé : 575 (niveau du Thunder God)" },
				{ kind = "sea", value = 1 },
			},
			steps = {
				"Rejoins les Skylands puis l'Upper Skylands (First Sea).",
				"Vaincs le Thunder God (niv. 575).",
				"Le drop est rare (≈6 % selon les guides) : recommence jusqu'à l'obtenir.",
			},
		},
		{
			id = "pole_v2",
			name = "Pole (2nd Form)",
			tag = "Pole V2",
			icon = "🌩️",
			sea = 3,
			summary = "Évolution du Pole (1st Form).",
			owned = { "Pole (2nd Form)" },
			reqs = {
				{ kind = "own", names = { "Pole (1st Form)" } },
				{ kind = "sea", value = 3, label = "Accès à la Rough Sea (Third Sea)" },
			},
			steps = {
				"Équipe le Pole (1st Form).",
				"Navigue dans la Rough Sea de la Third Sea.",
				"Être frappé par la foudre en tenant l'arme la transforme en Pole (2nd Form). C'est aléatoire.",
			},
			warning = "⚠ Sources contradictoires : d'anciens guides décrivent un échange au Thunder God (Rumble éveillé, Pole V1 à 180 de maîtrise, 5 000 Fragments). Vérifie en jeu avant de dépenser des ressources.",
		},
		{
			id = "saber",
			name = "Saber",
			tag = "Saber",
			icon = "🗡️",
			sea = 1,
			summary = "Épée obtenue au bout du puzzle du Saber Expert (First Sea).",
			owned = { "Saber" },
			reqs = {
				{ kind = "level", value = 200, label = "Niveau 200 (requis pour la dernière étape)" },
				{ kind = "sea", value = 1 },
			},
			steps = {
				"Jungle : appuie sur les 5 boutons verts (ordre libre).",
				"Prends la Torch au sous-sol près du lac, à côté du PNJ de quête de la Jungle.",
				"Desert : maison à moitié enterrée à porte rouge → sous-sol → brûle la porte brune avec la Torch → récupère la Cup.",
				"Frozen Village : remplis la Cup sous la stalactite qui goutte dans la grotte, puis donne-la au Sick Man.",
				"Pirate Village : le Rich Man a été volé ; vaincs le Mob Leader (niv. 120) sur la petite île au nord, puis récupère l'Ancient Relic.",
				"Jungle : utilise la Relic sur le symbole du mur du bâtiment en pierre et vaincs le Saber Expert.",
			},
		},
		{
			id = "rengoku",
			name = "Rengoku",
			tag = "Rengoku",
			icon = "🔥",
			sea = 2,
			summary = "Épée cachée dans l'Ice Castle (Second Sea), ouverte avec la Hidden Key.",
			owned = { "Rengoku" },
			reqs = {
				{ kind = "sea", value = 2 },
				{ kind = "level", value = 1400, label = "Niveau conseillé : 1400 (Awakened Ice Admiral)" },
				{ kind = "own", names = { "Hidden Key" }, label = "Posséder la Hidden Key" },
			},
			steps = {
				"Va à l'Ice Castle (Second Sea).",
				"Vaincs l'Awakened Ice Admiral : ≈5 % de chance de Hidden Key (doublée avec le gamepass 2x Boss Drops). Les Arctic Warriors et Snow Lurkers la lâchent aussi, très rarement.",
				"Avec la clé, entre dans la pièce cachée : sous l'escalier, à gauche du tapis rouge.",
				"Ouvre le coffre : Rengoku.",
			},
		},
		{
			id = "cdk",
			name = "Cursed Dual Katana",
			tag = "CDK",
			icon = "⚔️",
			sea = 3,
			summary = "Doubles katanas mythiques : nécessitent Yama et Tushita maîtrisés.",
			owned = { "Cursed Dual Katana" },
			reqs = {
				{ kind = "sea", value = 3 },
				{ kind = "level", value = 2200 },
				{ kind = "own", names = { "Yama" } },
				{ kind = "own", names = { "Tushita" } },
				{ kind = "mastery", name = "Yama", value = 350 },
				{ kind = "mastery", name = "Tushita", value = 350 },
			},
			steps = {
				"Yama : prends les quêtes de l'Elite Hunter (Castle on the Sea) et vaincs 30 Elite Pirates, puis retire Yama dans le temple derrière la cascade d'Hydra Island.",
				"Tushita : invoque rip_indra avec un God's Chalice et laisse-le en vie ; à la Floating Turtle, allume les torches dans l'ordre avec la Holy Torch (temps limité), puis vaincs Longma.",
				"Monte Yama et Tushita à 350 de maîtrise.",
				"Réussis les épreuves des parchemins de Yama et de Tushita : tu obtiens 6 Alucard Fragments.",
				"Place les fragments pour invoquer le Cursed Skeleton Boss et vaincs-le avec Yama ou Tushita.",
			},
			warning = "⚠ Certains guides indiquent 400 de maîtrise au lieu de 350 : vérifie le message du PNJ en jeu.",
		},
		{
			id = "godhuman",
			name = "Godhuman",
			tag = "Godhuman",
			icon = "👊",
			sea = 3,
			summary = "Style de combat vendu par l'Ancient Monk (Floating Turtle).",
			owned = { "Godhuman" },
			reqs = {
				{ kind = "sea", value = 3 },
				{ kind = "level", value = 1500 },
				{ kind = "mastery", name = "Superhuman", value = 400 },
				{ kind = "mastery", name = "Death Step", value = 400 },
				{ kind = "mastery", name = "Sharkman Karate", value = 400 },
				{ kind = "mastery", name = "Electric Claw", value = 400 },
				{ kind = "mastery", name = "Dragon Talon", value = 400 },
				{ kind = "material", name = "Fish Tail", value = 20 },
				{ kind = "material", name = "Magma Ore", value = 20 },
				{ kind = "material", name = "Dragon Scale", value = 10 },
				{ kind = "material", name = "Mystic Droplet", value = 10 },
				{ kind = "fragments", value = 5000 },
				{ kind = "beli", value = 5000000 },
			},
			steps = {
				"Monte Superhuman, Death Step, Sharkman Karate, Electric Claw et Dragon Talon à 400 de maîtrise (leurs styles de base doivent avoir été maîtrisés pour les débloquer).",
				"Fish Tail : Fishman Raiders / Captains (Floating Turtle).",
				"Magma Ore : ennemis de Hot and Cold / Magma Village.",
				"Dragon Scale : Dragon Crew (Hydra Island).",
				"Mystic Droplet : les lieux varient selon les guides, vérifie en jeu.",
				"Parle à l'Ancient Monk (Floating Turtle) et paie 5 000 000 Beli + 5 000 Fragments.",
			},
		},
		{
			id = "skull_guitar",
			name = "Skull Guitar",
			tag = "Skull Guitar",
			icon = "🎸",
			sea = 3,
			summary = "Arme à feu mythique (anciennement Soul Guitar), fabriquée à la Weird Machine.",
			owned = { "Skull Guitar", "Soul Guitar" },
			reqs = {
				{ kind = "sea", value = 3 },
				{ kind = "level", value = 2300 },
				{ kind = "material", name = "Bones", value = 500 },
				{ kind = "material", name = "Ectoplasm", value = 250 },
				{ kind = "material", name = "Dark Fragment", value = 1 },
				{ kind = "fragments", value = 5000 },
			},
			steps = {
				"Pendant la pleine lune, lance le puzzle au Haunted Castle (Third Sea).",
				"Résous les étapes du puzzle : tombes, fantômes, trophées puis tuyaux.",
				"Bones : ennemis du Haunted Castle. Ectoplasm : Cursed Ship (Second Sea). Dark Fragment : Darkbeard (Second Sea).",
				"Fabrique la Skull Guitar à la Weird Machine (sous-sol du Haunted Castle).",
			},
		},
	}

	local Equipment = { cards = {}, ITEMS = ITEMS }

	local page
	local function refreshBadges()
		local ctx = Info:context()
		for _, entry in ipairs(ITEMS) do
			local card = Equipment.cards[entry.id]
			if card then
				local sum = Req.summarize(entry.reqs, ctx)
				local owned = Req.evaluate({ kind = "own", names = entry.owned }, ctx) == "ok"
				if owned then
					card.setBadge("Possédé", Color3.fromRGB(28, 90, 56))
				else
					card.setBadge(("%d %%"):format(math.floor(sum.ratio * 100 + 0.5)))
				end
				if card.open then
					card.rebuild()
				end
			end
		end
	end
	Equipment.refresh = refreshBadges

	page = UI:addPage("equipment", {
		title = "Équipements",
		subtitle = "Prérequis, étapes et ressources manquantes",
		icon = "⚔️",
		order = 3,
		onShow = refreshBadges,
	})
	local root = page.frame

	-- Lecture d'inventaire à la demande (nécessaire pour les matériaux et objets rangés).
	local invCard = c.card(root)
	local invLabel = c.label(invCard, "", { muted = true, size = 12 })
	local function updateInvLabel()
		local inv = Hub.Modules.inventory
		if not inv then
			invLabel.Text = "Lecture d'inventaire désactivée dans les paramètres : seuls ton sac et ton arme en main sont vérifiés."
		elseif inv.scanned then
			invLabel.Text = "Inventaire analysé. Les matériaux et objets rangés sont pris en compte."
		else
			invLabel.Text = "Les matériaux et objets rangés s'affichent en « ? » tant que l'inventaire n'est pas analysé (lecture seule)."
		end
	end
	updateInvLabel()
	if Hub.Modules.inventory then
		local row = c.row(invCard)
		c.button(row, "Analyser mon inventaire", function()
			invLabel.Text = "Analyse en cours…"
			Hub.Modules.inventory:scan(function(ok, msg)
				updateInvLabel()
				Hub.notify(ok and "Inventaire analysé" or "Inventaire", msg, ok and "success" or "warn", 4)
			end)
		end, { accent = true, width = 200 })
		Hub.Modules.inventory:onUpdate(function()
			if UI.current == "equipment" then
				refreshBadges()
			end
		end)
	end

	c.section(root, "Équipements")
	for _, entry in ipairs(ITEMS) do
		local card = c.collapsible(root, entry.name, (Info.SEA_NAMES[entry.sea] or "") .. "  ·  " .. entry.tag, function(body)
			Req.render(body, entry, Info:context())
		end, { icon = entry.icon, badge = "—" })
		Equipment.cards[entry.id] = card
		UI:addSearch(entry.name, entry.tag .. " equipement arme " .. (entry.summary or ""), "equipment", card.frame)
	end

	c.label(root, "✓ vérifié  ·  ✗ manquant  ·  ? non vérifiable par script (à confirmer en jeu).", { muted = true, size = 11 })
	c.label(root, "Sources : guides publics vérifiés le 17/10/2026. Le jeu évolue : en cas de doute, vérifie en jeu.", { muted = true, size = 11 })

	return Equipment
end
