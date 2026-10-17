-- BloxHub / progression : objectifs, déblocages, maîtrises, boss et guide des Seas.
-- Données vérifiées le 17/10/2026 à partir de guides publics (wiki Fandom Blox Fruits,
-- KeenGamer, Beebom, Deltia's Gaming, Pro Game Guides…). Les points où les sources
-- divergent sont marqués « ⚠ à vérifier ».

return function(Hub)
	local UI = Hub.Modules.ui
	local Info = Hub.Modules.player_info
	local c = UI.c
	local fmt = Info.format

	local MAX_MASTERY = 600

	local Progression = {}

	-- Déblocages par niveau (niveau minimal requis ou conseillé par le jeu).
	local UNLOCKS = {
		{ level = 200, sea = 1, text = "Saber : puzzle du Saber Expert (Jungle)" },
		{ level = 575, sea = 1, text = "Thunder God (Upper Skylands) : chance de Pole (1st Form)" },
		{ level = 700, sea = 1, text = "Second Sea : quête du Military Detective puis Ice Admiral" },
		{ level = 850, sea = 2, text = "Quête du Colisée (Bartilo) puis Race V2 chez l'Alchimiste" },
		{ level = 1000, sea = 2, text = "Race Ghoul (Experimic, Cursed Ship)" },
		{ level = 1500, sea = 2, text = "Third Sea : Don Swan → King Red Head → rip_indra → Mr. Captain" },
		{ level = 2200, sea = 3, text = "Puzzle du Cursed Dual Katana" },
		{ level = 2300, sea = 3, text = "Puzzle de la Skull Guitar (pleine lune)" },
	}

	local BOSSES = {
		{ "Saber Expert", 1, 200, "Jungle", "Fin du puzzle du Saber → Saber." },
		{ "Thunder God", 1, 575, "Upper Skylands", "Drop rare : Pole (1st Form)." },
		{ "Ice Admiral", 1, 700, "Frozen Village", "Étape de la quête d'accès à la Second Sea." },
		{ "Don Swan", 2, 1000, "Mansion (Kingdom of Rose)", "Salle ouverte par Trevor contre un fruit de plus de 1 000 000 Beli. Requis pour les Race V3 et la Third Sea." },
		{ "Darkbeard", 2, 1000, "Dark Arena", "Invoqué avec un Fist of Darkness. Drop : Dark Fragment (Skull Guitar)." },
		{ "Cursed Captain", 2, 1325, "Cursed Ship", "Drop : Hellfire Torch (race Ghoul)." },
		{ "Awakened Ice Admiral", 2, 1400, "Ice Castle", "Drop ≈5 % : Hidden Key (Rengoku), x2 avec le gamepass 2x Boss Drops." },
		{ "rip_indra", 2, 1500, "Île d'Indra (via King Red Head)", "Le réduire à 50 % de vie lance la cinématique d'accès à la Third Sea." },
		{ "Longma", 3, 2000, "Floating Turtle", "Après le puzzle des torches : Tushita." },
		{ "Dough King", 3, 2300, "Sea of Treats", "Drop : Mirror Fractal (Race V4)." },
		{ "rip_indra True Form", 3, 5000, "Castle on the Sea", "Invoqué avec un God's Chalice ; nécessaire pour Tushita et la Race V4." },
		{ "Cursed Skeleton Boss", 3, nil, "Puzzle du CDK", "Invoqué avec les 6 Alucard Fragments → Cursed Dual Katana." },
	}

	local SEAS = {
		{
			name = "First Sea",
			range = "Niveaux 1 → 700",
			steps = {
				"Monte jusqu'au niveau 700 en suivant les quêtes des îles dans l'ordre.",
				"Parle au Military Detective (Prison) pour obtenir une clé.",
				"Ouvre la porte de la grotte de Frozen Village et vaincs l'Ice Admiral.",
				"Retourne voir le Military Detective puis l'Experienced Captain à Middle Town : il t'emmène en Second Sea.",
			},
		},
		{
			name = "Second Sea",
			range = "Niveaux 700 → 1500",
			steps = {
				"Niveau 850 : quête du Colisée (Bartilo au Café, Kingdom of Rose) — débloque la Race V2.",
				"Vaincs Don Swan (salle ouverte par Trevor contre un fruit valant plus de 1 000 000 Beli).",
				"Au niveau 1500, appuie sur les 8 boutons devant la cellule de King Red Head (Colisée) dans le bon ordre.",
				"Combats rip_indra jusqu'à 50 % de sa vie pour déclencher la cinématique.",
				"Parle à Mr. Captain (Green Zone) pour partir en Third Sea.",
			},
		},
		{
			name = "Third Sea",
			range = "Niveaux 1500 → max",
			steps = {
				"Continue les quêtes des îles (Port Town, Hydra Island, Great Tree, Floating Turtle, Haunted Castle, Sea of Treats…).",
				"Contenus de fin de jeu : Godhuman, Cursed Dual Katana, Skull Guitar, Race V4.",
				"Les Fragments viennent surtout des raids : garde-les pour Godhuman (5 000) et la Skull Guitar (5 000).",
			},
		},
	}

	local page = UI:addPage("progression", {
		title = "Progression",
		subtitle = "Objectifs, déblocages, maîtrises et boss",
		icon = "📈",
		order = 2,
		onShow = function()
			Progression:refresh()
		end,
	})
	local root = page.frame

	c.section(root, "Tes prochains objectifs")
	local objectivesCard = c.card(root, { gap = 8 })
	UI:addSearch("Objectifs du joueur", "objectif prochain but", "progression", objectivesCard)

	c.section(root, "Conditions de déblocage")
	local unlocksCard = c.card(root, { gap = 4 })
	UI:addSearch("Conditions de déblocage", "niveau requis debloquer", "progression", unlocksCard)

	c.section(root, "Suivi des maîtrises")
	local masteryCard = c.card(root, { gap = 8 })
	UI:addSearch("Suivi des maîtrises", "mastery maitrise armes styles", "progression", masteryCard)

	local function clear(frame)
		for _, child in ipairs(frame:GetChildren()) do
			if child:IsA("GuiObject") then
				child:Destroy()
			end
		end
	end

	local function objectives(s)
		local out = {}
		local lv, sea = s.level, s.sea
		if not lv or not sea then
			table.insert(out, { text = "Données indisponibles : lance le hub dans Blox Fruits.", ratio = 0, right = "—" })
			return out
		end
		local function goal(text, current, target)
			table.insert(out, { text = text, ratio = current / target, right = fmt(current) .. " / " .. fmt(target) })
		end
		if sea == 1 then
			if lv < 200 then
				goal("Niveau 200 : puzzle du Saber", lv, 200)
			end
			if lv < 700 then
				goal("Niveau 700 : accès à la Second Sea", lv, 700)
			else
				table.insert(out, { text = "Débloquer la Second Sea : Military Detective → Ice Admiral → Experienced Captain", ratio = 1, right = "prêt" })
			end
		elseif sea == 2 then
			if lv < 850 then
				goal("Niveau 850 : quête du Colisée et Race V2", lv, 850)
			end
			if lv < 1500 then
				goal("Niveau 1500 : accès à la Third Sea", lv, 1500)
			else
				table.insert(out, { text = "Débloquer la Third Sea : Don Swan → King Red Head → rip_indra → Mr. Captain", ratio = 1, right = "prêt" })
			end
			if s.beli then
				goal("2 000 000 Beli pour une Race V3 (Arowe)", math.min(s.beli, 2000000), 2000000)
			end
		elseif sea == 3 then
			if lv < 2200 then
				goal("Niveau 2200 : puzzle du Cursed Dual Katana", lv, 2200)
			end
			if lv < 2300 then
				goal("Niveau 2300 : puzzle de la Skull Guitar", lv, 2300)
			end
			if s.fragments then
				goal("5 000 Fragments (Godhuman ou Skull Guitar)", math.min(s.fragments, 5000), 5000)
			end
			if s.beli then
				goal("5 000 000 Beli pour Godhuman", math.min(s.beli, 5000000), 5000000)
			end
		end
		return out
	end

	local function renderMasteries()
		clear(masteryCard)
		local tools = Info:tools()
		if #tools == 0 then
			c.label(masteryCard, "Aucun objet dans ton sac pour l'instant.", { muted = true })
		else
			table.sort(tools, function(a, b)
				return (a.mastery or 0) > (b.mastery or 0)
			end)
			for _, t in ipairs(tools) do
				local name = t.name .. (t.kind and ("  ·  " .. t.kind) or "") .. (t.equipped and "  (en main)" or "")
				if t.mastery then
					c.progress(masteryCard, name, t.mastery / MAX_MASTERY, fmt(t.mastery) .. " / " .. MAX_MASTERY)
				else
					c.progress(masteryCard, name, 0, "non lisible")
				end
			end
		end
		c.label(masteryCard, "Seuls les objets présents dans ton sac ou en main sont lisibles. Maîtrise max : 600.", { muted = true, size = 11 })
		local row = c.row(masteryCard)
		c.button(row, "Actualiser", function()
			renderMasteries()
		end, { width = 120 })
	end

	function Progression:refresh()
		local s = Info:snapshot()
		clear(objectivesCard)
		for _, o in ipairs(objectives(s)) do
			c.progress(objectivesCard, o.text, o.ratio, o.right)
		end

		clear(unlocksCard)
		for _, u in ipairs(UNLOCKS) do
			local status = "unknown"
			if s.level then
				status = s.level >= u.level and "ok" or "missing"
			end
			c.status(unlocksCard, status, ("Niv. %s — %s"):format(fmt(u.level), u.text), Info.SEA_NAMES[u.sea])
		end

		renderMasteries()
	end

	-- Boss (statique)
	c.section(root, "Informations sur les boss")
	for _, b in ipairs(BOSSES) do
		local name, sea, level, place, note = b[1], b[2], b[3], b[4], b[5]
		local card = c.collapsible(root, name, Info.SEA_NAMES[sea] .. "  ·  " .. place, function(body)
			c.status(body, "ok", "Niveau", level and fmt(level) or "variable")
			c.status(body, "ok", "Lieu", place .. " (" .. Info.SEA_NAMES[sea] .. ")")
			c.label(body, note)
		end, { icon = "💀", badge = level and ("Niv. " .. fmt(level)) or "Puzzle" })
		UI:addSearch(name, "boss " .. place .. " " .. note, "progression", card.frame)
	end

	-- Guide des Seas (statique)
	c.section(root, "Guide des Seas")
	for i, sea in ipairs(SEAS) do
		local card = c.collapsible(root, sea.name, sea.range, function(body)
			for n, step in ipairs(sea.steps) do
				c.label(body, ("%d. %s"):format(n, step))
			end
		end, { icon = ({ "🌊", "🌀", "🌋" })[i], badge = "Sea " .. i })
		UI:addSearch(sea.name, "sea mer acces debloquer " .. table.concat(sea.steps, " "), "progression", card.frame)
	end

	c.label(root, "Sources : guides publics vérifiés le 17/10/2026. Le jeu évolue : en cas de doute, vérifie en jeu.", { muted = true, size = 11 })

	return Progression
end
