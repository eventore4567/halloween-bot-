-- BloxHub / dashboard : vue d'ensemble du joueur et état des modules.
-- Le rafraîchissement ne tourne que lorsque la page est visible.

return function(Hub)
	local UI = Hub.Modules.ui
	local Tasks = Hub.Modules.tasks
	local Config = Hub.Modules.config
	local Info = Hub.Modules.player_info
	local c, Theme = UI.c, UI.Theme
	local fmt = Info.format

	local TASK = "dashboard.refresh"
	local Dashboard = {}

	local page = UI:addPage("dashboard", {
		title = "Dashboard",
		subtitle = "Ton compte en un coup d'œil",
		icon = "🏠",
		order = 1,
		onShow = function()
			Dashboard:start()
		end,
		onHide = function()
			Tasks:stop(TASK)
		end,
	})
	local root = page.frame

	local warnCard = c.card(root, { color = Color3.fromRGB(48, 38, 18) })
	local warnLabel = c.label(warnCard, "", { color = Theme.warn })
	warnCard.Visible = false

	c.section(root, "Joueur")
	local tile = c.grid(root, 3, 62)
	local setLevel = tile("Niveau")
	local setSea = tile("Sea actuelle")
	local setRace = tile("Race")
	local setBeli = tile("Beli")
	local setFrag = tile("Fragments")
	local setFruit = tile("Fruit")

	c.section(root, "Arme équipée")
	local weaponCard = c.card(root)
	local weaponLabel = c.label(weaponCard, "—", { bold = true, size = 14 })
	local setWeaponMastery = c.progress(weaponCard, "Maîtrise", 0, "—")

	c.section(root, "État des modules")
	local modulesCard = c.card(root, { gap = 4 })
	local moduleRows = {}

	local MODULE_LABELS = {
		{ "dashboard", "Dashboard" },
		{ "progression", "Progression" },
		{ "equipment", "Équipements" },
		{ "races", "Races" },
		{ "inventory", "Lecture d'inventaire" },
		{ "notifications", "Notifications" },
		{ "diagnostics", "Diagnostic" },
	}

	local function moduleStatus(id)
		local st = Hub.ModuleStatus[id]
		if id == "dashboard" then
			st = "actif"
		end
		if st == "actif" then
			if id == "notifications" and not Config:get("notifications") then
				return "unknown", "coupées dans les paramètres"
			end
			return "ok", "actif"
		elseif st == "désactivé" then
			return "unknown", "désactivé"
		elseif st == nil then
			return "unknown", "en attente"
		end
		return "missing", st
	end

	local function refreshModules()
		for _, row in ipairs(moduleRows) do
			row:Destroy()
		end
		table.clear(moduleRows)
		for _, pair in ipairs(MODULE_LABELS) do
			local status, detail = moduleStatus(pair[1])
			local row = c.status(modulesCard, status, pair[2], detail)
			table.insert(moduleRows, row)
		end
	end

	function Dashboard:refresh()
		local s = Info:snapshot()
		if not Info:isBloxFruits() then
			warnCard.Visible = true
			warnLabel.Text = ("Jeu non reconnu (PlaceId %s). Lance le hub dans Blox Fruits pour voir tes infos."):format(tostring(s.placeId))
		elseif not s.dataReady then
			warnCard.Visible = true
			warnLabel.Text = "Données du joueur pas encore chargées (choisis ton équipe si ce n'est pas fait)."
		else
			warnCard.Visible = false
		end
		setLevel(s.level and fmt(s.level) or "—")
		setSea(s.seaName or "—")
		setRace(s.race and (s.race .. (s.raceVersion and (" V" .. s.raceVersion) or "")) or "—")
		setBeli(s.beli and fmt(s.beli) or "—", Theme.ok)
		setFrag(s.fragments and fmt(s.fragments) or "—", Color3.fromRGB(196, 167, 255))
		setFruit(s.fruit or "Aucun")
		if s.weapon then
			weaponLabel.Text = s.weapon
			if s.weaponMastery then
				setWeaponMastery(s.weaponMastery / 600, fmt(s.weaponMastery) .. " / 600")
			else
				setWeaponMastery(0, "non lisible")
			end
		else
			weaponLabel.Text = "Aucune arme en main"
			setWeaponMastery(0, "—")
		end
	end

	function Dashboard:start()
		refreshModules()
		Tasks:loop(TASK, function()
			return Config:get("refreshInterval")
		end, function()
			if not UI.visible or UI.minimized or UI.current ~= "dashboard" then
				Tasks:stop(TASK)
				return
			end
			Dashboard:refresh()
		end)
	end

	UI:addSearch("Niveau, Beli, Fragments", "level argent race sea fruit", "dashboard", nil)
	UI:addSearch("Arme équipée et maîtrise", "mastery arme", "dashboard", weaponCard)
	UI:addSearch("État des modules", "modules statut", "dashboard", modulesCard)

	function Dashboard:destroy()
		Tasks:stop(TASK)
	end

	return Dashboard
end
