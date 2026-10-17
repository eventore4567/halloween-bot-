-- BloxHub / settings : pages Paramètres et Diagnostic.

return function(Hub)
	local UI = Hub.Modules.ui
	local Config = Hub.Modules.config
	local Diag = Hub.Modules.diagnostics
	local Tasks = Hub.Modules.tasks
	local Compat = Hub.Modules.compat
	local c, Theme = UI.c, UI.Theme

	local Settings = {}

	---------------------------------------------------------------------------
	-- Paramètres
	---------------------------------------------------------------------------
	local page = UI:addPage("settings", {
		title = "Paramètres",
		subtitle = "Interface, modules et sécurité",
		icon = "⚙️",
		order = 10,
	})
	local root = page.frame

	c.section(root, "Interface")
	local ui = c.card(root, { gap = 2 })
	c.toggle(ui, "Notifications", Config:get("notifications"), function(v)
		Config:set("notifications", v)
	end, "Petites alertes en bas à droite")
	c.toggle(ui, "Animations", Config:get("animations"), function(v)
		Config:set("animations", v)
	end, "Désactive-les pour un rendu plus léger")
	c.choice(ui, "Taille de l'interface", {
		{ label = "Petite (85 %)", value = 0.85 },
		{ label = "Normale", value = 1 },
		{ label = "Grande (115 %)", value = 1.15 },
	}, Config:get("uiScale"), function(v)
		Config:set("uiScale", v)
	end)
	c.choice(ui, "Rafraîchissement Dashboard", {
		{ label = "1 seconde", value = 1 },
		{ label = "2 secondes", value = 2 },
		{ label = "5 secondes", value = 5 },
	}, Config:get("refreshInterval"), function(v)
		Config:set("refreshInterval", v)
	end)
	c.choice(ui, "Touche afficher / masquer", {
		{ label = "RightShift", value = "RightShift" },
		{ label = "RightControl", value = "RightControl" },
		{ label = "F6", value = "F6" },
		{ label = "Insert", value = "Insert" },
	}, Config:get("toggleKey"), function(v)
		Config:set("toggleKey", v)
	end)
	UI:addSearch("Notifications et animations", "parametres interface taille touche raccourci", "settings", ui)

	c.section(root, "Modules")
	local mods = c.card(root, { gap = 2 })
	c.label(mods, "Chaque module peut être désactivé. Le changement s'applique au rechargement.", { muted = true, size = 12 })
	local MODULES = {
		{ "dashboard", "Dashboard", "Vue d'ensemble du compte" },
		{ "progression", "Progression", "Objectifs, maîtrises, boss, Seas" },
		{ "equipment", "Équipements", "Fiches Pole, Saber, CDK, Godhuman…" },
		{ "races", "Races", "Fiches V2 / V3 / V4" },
		{ "inventory", "Lecture d'inventaire", "Analyse à la demande, lecture seule" },
	}
	local pendingReload = false
	for _, m in ipairs(MODULES) do
		c.toggle(mods, m[2], Config:moduleEnabled(m[1]), function(v)
			Config:setModule(m[1], v)
			if not pendingReload then
				pendingReload = true
				Hub.notify("Rechargement nécessaire", "Clique sur « Recharger le hub » pour appliquer.", "info", 5)
			end
		end, m[3])
	end
	UI:addSearch("Activer / désactiver les modules", "modules parametres", "settings", mods)

	c.section(root, "Actions")
	local actions = c.card(root, { gap = 8 })
	local row1 = c.row(actions)
	c.button(row1, "Recharger le hub", function()
		Hub.Reload()
	end, { accent = true, width = 170 })
	c.button(row1, "Réinitialiser", function()
		Config:reset()
		Hub.notify("Paramètres réinitialisés", "Recharge le hub pour tout appliquer.", "info", 4)
	end, { width = 130 })
	local row2 = c.row(actions)
	c.button(row2, "⏻  Arrêt d'urgence", function()
		Hub.Shutdown("arrêt d'urgence")
	end, { danger = true, width = 170 })
	c.label(actions, "L'arrêt d'urgence coupe immédiatement toutes les tâches et connexions et ferme le hub.", { muted = true, size = 11 })
	c.label(actions, Config.persistent and "Paramètres sauvegardés dans BloxHub/config.json." or "Ton exécuteur ne gère pas les fichiers : paramètres gardés pour cette session seulement.", { muted = true, size = 11 })
	UI:addSearch("Arrêt d'urgence", "stop quitter fermer urgence", "settings", actions)
	UI:addSearch("Recharger le hub", "reload relancer", "settings", actions)

	---------------------------------------------------------------------------
	-- Diagnostic
	---------------------------------------------------------------------------
	local DIAG_TASK = "diagnostic.refresh"
	local diagPage
	diagPage = UI:addPage("diagnostic", {
		title = "Diagnostic",
		subtitle = "Compatibilité, tâches et journal technique",
		icon = "🩺",
		order = 11,
		onShow = function()
			Settings:refreshDiag()
			Tasks:loop(DIAG_TASK, 3, function()
				if UI.current ~= "diagnostic" or not UI.visible or UI.minimized then
					Tasks:stop(DIAG_TASK)
					return
				end
				Settings:refreshDiag()
			end)
		end,
		onHide = function()
			Tasks:stop(DIAG_TASK)
		end,
	})
	local droot = diagPage.frame

	c.section(droot, "Environnement")
	local envCard = c.card(droot, { gap = 4 })
	c.status(envCard, "ok", "Exécuteur", Compat.executor)
	c.status(envCard, "ok", "Version du hub", Hub.Version)
	c.status(envCard, "ok", "Interface attachée à", UI.parentMode)
	local pi = Hub.Modules.player_info
	c.status(envCard, pi:isBloxFruits() and "ok" or "warn", "Jeu", pi:isBloxFruits() and "Blox Fruits reconnu" or ("PlaceId " .. tostring(game.PlaceId) .. " non reconnu"))

	c.section(droot, "Compatibilité des API")
	local compatCard = c.card(droot, { gap = 4 })
	for _, chk in ipairs(Compat.checks) do
		c.status(compatCard, chk.ok and "ok" or "missing", chk.label, chk.detail or (chk.ok and "disponible" or "indisponible : fonction désactivée"))
	end
	UI:addSearch("Compatibilité des API", "opiumware executeur api compat", "diagnostic", compatCard)

	c.section(droot, "Modules")
	local modCard = c.card(droot, { gap = 4 })
	for _, name in ipairs({ "compat", "diagnostics", "tasks", "config", "ui", "notifications", "requirements", "player_info", "inventory", "dashboard", "progression", "equipment", "races", "settings" }) do
		local st = Hub.ModuleStatus[name] or (name == "settings" and "actif") or "en attente"
		local status = st == "actif" and "ok" or (st == "désactivé" and "unknown" or "missing")
		c.status(modCard, status, name, st)
	end

	c.section(droot, "Ressources")
	local resCard = c.card(droot, { gap = 4 })
	local resLabel = c.label(resCard, "", { size = 12 })

	c.section(droot, "Journal technique")
	local logCard = c.card(droot, { gap = 2 })
	local logLabel = c.label(logCard, "", { size = 11, rich = false })
	logLabel.Font = Enum.Font.Code
	local logRow = c.row(logCard)
	if Compat:has("clipboard") then
		c.button(logRow, "Copier le journal", function()
			local ok = Compat:copy(Diag:dump())
			Hub.notify(ok and "Journal copié" or "Copie impossible", nil, ok and "success" or "warn", 3)
		end, { width = 160 })
	end
	c.button(logRow, "Tester une erreur", function()
		Diag:safe("test manuel", function()
			error("erreur de test volontaire (aucun impact)")
		end)
		Settings:refreshDiag()
		Hub.notify("Erreur de test capturée", "Visible dans le journal ci-dessous.", "info", 3)
	end, { width = 160 })
	UI:addSearch("Journal technique", "log erreurs diagnostic", "diagnostic", logCard)

	function Settings:refreshDiag()
		local tasks = Tasks:list()
		local names = {}
		for _, t in ipairs(tasks) do
			table.insert(names, t.name)
		end
		local mem = Diag:memoryKB()
		resLabel.Text = table.concat({
			("Tâches actives : %d %s"):format(#tasks, #names > 0 and ("(" .. table.concat(names, ", ") .. ")") or ""),
			("Connexions actives : %d"):format(Tasks:connectionCount()),
			("Mémoire Lua : %s"):format(mem and (("%.1f Mo"):format(mem / 1024)) or "indisponible"),
			("Journal : %d info · %d avert. · %d erreurs"):format(Diag.counts.INFO or 0, Diag.counts.WARN or 0, Diag.counts.ERROR or 0),
		}, "\n")
		local lines = {}
		for _, e in ipairs(Diag:recent(25)) do
			table.insert(lines, ("[%s] %s %s"):format(e.t, e.level, e.msg:sub(1, 160)))
		end
		logLabel.Text = #lines > 0 and table.concat(lines, "\n") or "(vide)"
		logLabel.TextColor3 = (Diag.counts.ERROR or 0) > 0 and Color3.fromRGB(230, 200, 200) or Theme.muted
	end

	function Settings:destroy()
		Tasks:stop(DIAG_TASK)
	end

	return Settings
end
