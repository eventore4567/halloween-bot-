--!nocheck
-- Tests BloxHub dans l'environnement Roblox simulé (tests/mock_roblox.luau).
-- Lancement : sh tests/run.sh

local mock = require("./mock_roblox")
local SOURCES = require("./_sources")

local REPO = "https://raw.githubusercontent.com/eventore4567/halloween-bot-/refs/heads/"
local BRANCH = "bloxhub"

local passed, failed = 0, 0
local failures = {}

local function check(cond, name, detail)
	if cond then
		passed += 1
	else
		failed += 1
		table.insert(failures, name .. (detail and (" — " .. tostring(detail)) or ""))
		print("  ✗ " .. name .. (detail and (" — " .. tostring(detail)) or ""))
	end
end

local function section(name)
	print("\n▶ " .. name)
end

-- Sources servies par le faux game:HttpGet. mutate(name, body) pour simuler des pannes.
local function sources(ref, mutate)
	local map = {}
	local base = REPO .. ref .. "/"
	for path, body in pairs(SOURCES) do
		local b = body
		if mutate then
			b = mutate(path, body)
		end
		if b ~= nil then
			map[base .. path] = b
		end
	end
	return map
end

local DEFAULT_PLAYER = {
	level = 2350,
	beli = 3200000,
	fragments = 4100,
	race = "Skypiea",
	fruit = "Dough-Dough",
	tools = {
		{ name = "Godhuman", mastery = 120, tip = "Melee", equipped = true },
		{ name = "Yama", mastery = 410, tip = "Sword" },
		{ name = "Tushita", mastery = 200, tip = "Sword" },
		{ name = "Dough-Dough", mastery = 380, tip = "Blox Fruit" },
	},
}

local INVENTORY = {
	{ Name = "Bones", Type = "Material", Count = 520 },
	{ Name = "Ectoplasm", Type = "Material", Count = 90 },
	{ Name = "Fish Tail", Type = "Material", Count = 25 },
	{ Name = "Magma Ore", Type = "Material", Count = 3 },
	{ Name = "Yama", Type = "Sword", Mastery = 410 },
	{ Name = "Tushita", Type = "Sword", Mastery = 200 },
	{ Name = "Saber", Type = "Sword", Mastery = 600 },
}

local function boot(opts)
	opts = opts or {}
	if opts.player == nil then
		opts.player = DEFAULT_PLAYER
	elseif opts.player == false then
		opts.player = nil
	end
	if opts.inventory == nil then
		opts.inventory = INVENTORY
	elseif opts.inventory == false then
		opts.inventory = nil
	end
	opts.sources = opts.sources or sources(BRANCH)
	local world = opts.world or mock.world(opts)
	if opts.world then
		-- même monde (relance) : on met à jour les sources servies
		world = opts.world
	end
	mock.exec(world, SOURCES["loader.lua"], "=loader")
	mock.advance(opts.wait or 2)
	return world, world.genv.BloxHub
end

local function descendants(root)
	return root:GetDescendants()
end

local function findText(root, pattern, class)
	for _, d in ipairs(descendants(root)) do
		if (not class or d.ClassName == class) and (d.ClassName == "TextLabel" or d.ClassName == "TextButton" or d.ClassName == "TextBox") then
			if string.find(d.Text, pattern, 1, true) then
				return d
			end
		end
	end
	return nil
end

local function click(button)
	assert(button, "bouton introuvable")
	mock.advance(0.3)
	button.MouseButton1Click:Fire()
	mock.advance(0.1)
end

local function diagErrors(hub)
	return hub and hub.Modules.diagnostics and hub.Modules.diagnostics.counts.ERROR or 0
end

local function lastErrors(hub, n)
	local out = {}
	for _, e in ipairs(hub.Modules.diagnostics:recent(n or 5)) do
		if e.level == "ERROR" then
			table.insert(out, e.msg)
		end
	end
	return table.concat(out, "\n")
end

local function noScriptErrors(label)
	check(#mock.errors == 0, label .. " : aucune erreur non capturée", mock.errors[1])
	table.clear(mock.errors)
end

---------------------------------------------------------------------------
section("Chargement normal")
---------------------------------------------------------------------------
local world, hub = boot()
check(hub ~= nil, "le hub est créé")
check(hub and hub.Running, "le hub tourne")
for _, name in ipairs({ "compat", "diagnostics", "tasks", "config", "ui", "notifications", "requirements", "player_info", "inventory", "dashboard", "progression", "equipment", "races", "automation", "settings" }) do
	check(hub.ModuleStatus[name] == "actif", "module " .. name .. " actif", hub.ModuleStatus[name])
end
check(world.genv.BloxHubLoading == nil, "verrou de chargement libéré")
local UI = hub.Modules.ui
check(UI.gui.Parent == world.hidden, "interface attachée via gethui")
check(UI.window.Visible, "fenêtre visible")
check(UI.current == "dashboard", "page Dashboard ouverte au démarrage", UI.current)
check(diagErrors(hub) == 0, "aucune erreur au démarrage", lastErrors(hub))
noScriptErrors("démarrage")
check(#world.log.http == 15, "15 modules téléchargés", #world.log.http)

---------------------------------------------------------------------------
section("Dashboard")
---------------------------------------------------------------------------
mock.advance(0.5)
check(findText(UI.window, "2 350") ~= nil, "niveau affiché (2 350)")
local seaTitle = findText(UI.pages.dashboard.frame, "Sea actuelle", "TextLabel")
check(seaTitle and seaTitle.Parent.Value.Text == "First Sea", "Sea détectée depuis le PlaceId (First Sea)", seaTitle and seaTitle.Parent.Value.Text)
check(findText(UI.window, "Angel (Skypiea)") ~= nil, "race traduite Skypiea → Angel")
check(findText(UI.window, "3 200 000") ~= nil, "Beli affichés")
check(findText(UI.window, "4 100") ~= nil, "Fragments affichés")
check(findText(UI.window, "Godhuman") ~= nil, "arme équipée affichée")
check(findText(UI.window, "120 / 600") ~= nil, "maîtrise de l'arme affichée")
check(hub.Modules.tasks:isRunning("dashboard.refresh"), "rafraîchissement actif quand la page est visible")
-- Le niveau change : la valeur doit suivre au prochain rafraîchissement.
world.player.Data.Level.Value = 2400
mock.advance(2.5)
check(findText(UI.window, "2 400") ~= nil, "le niveau est mis à jour en direct")

---------------------------------------------------------------------------
section("Navigation")
---------------------------------------------------------------------------
for _, id in ipairs({ "progression", "equipment", "races", "automation", "settings", "diagnostic", "dashboard" }) do
	local page = UI.pages[id]
	check(page and page.navButton, "bouton de navigation " .. id)
	click(page.navButton)
	check(UI.current == id, "navigation vers " .. id, UI.current)
	check(page.frame.Visible, "page " .. id .. " visible")
	local others = 0
	for _, p in ipairs(UI.pageList) do
		if p.id ~= id and p.frame.Visible then
			others += 1
		end
	end
	check(others == 0, "une seule page visible (" .. id .. ")", others)
end
check(not hub.Modules.tasks:isRunning("diagnostic.refresh"), "la tâche Diagnostic s'arrête en quittant la page")
check(diagErrors(hub) == 0, "aucune erreur pendant la navigation", lastErrors(hub))

---------------------------------------------------------------------------
section("Progression")
---------------------------------------------------------------------------
click(UI.pages.progression.navButton)
local prog = UI.pages.progression.frame
check(findText(prog, "Niveau 700 : accès") == nil, "objectifs First Sea non adaptés au niveau 2400 masqués")
check(findText(prog, "Débloquer la Second Sea") ~= nil, "objectif d'accès à la Second Sea proposé")
check(findText(prog, "Yama") ~= nil, "maîtrise de Yama listée")
check(findText(prog, "410 / 600") ~= nil, "valeur de maîtrise Yama")
local bossCard = findText(prog, "Dough King", "TextLabel")
check(bossCard ~= nil, "fiche boss Dough King")
-- ouvrir toutes les cartes repliables de la page
local opened = 0
for _, d in ipairs(descendants(prog)) do
	if d.ClassName == "TextButton" and d.Size.Y.Offset == 52 then
		click(d)
		opened += 1
	end
end
check(opened >= 15, "toutes les cartes boss / seas s'ouvrent", opened)
check(findText(prog, "Military Detective (Prison)") ~= nil, "guide First Sea affiché")
check(diagErrors(hub) == 0, "aucune erreur dans Progression", lastErrors(hub))

---------------------------------------------------------------------------
section("Équipements et inventaire")
---------------------------------------------------------------------------
click(UI.pages.equipment.navButton)
local equip = UI.pages.equipment.frame
local eq = hub.Modules.equipment
check(eq.cards.cdk ~= nil and eq.cards.godhuman ~= nil and eq.cards.skull_guitar ~= nil, "fiches CDK / Godhuman / Skull Guitar")
for _, id in ipairs({ "pole_v1", "pole_v2", "saber", "rengoku", "cdk", "godhuman", "skull_guitar" }) do
	local card = eq.cards[id]
	check(card ~= nil, "fiche " .. id)
	card.setOpen(true)
end
check(findText(equip, "Prérequis") ~= nil, "section Prérequis affichée")
check(findText(equip, "Ressources manquantes") ~= nil, "section Ressources manquantes affichée")
check(findText(equip, "Tushita (maîtrise) : il manque 150") ~= nil, "CDK : maîtrise Tushita manquante calculée (350 - 200)")
check(findText(equip, "Fragments : il manque 900") ~= nil, "Fragments manquants calculés (5 000 - 4 100)")
check(findText(equip, "Beli : il manque 1 800 000") ~= nil, "Beli manquants pour Godhuman")
check(findText(equip, "analyse l'inventaire pour vérifier") ~= nil, "matériaux en « ? » avant analyse")

local scanBtn = findText(equip, "Analyser mon inventaire", "TextButton")
check(scanBtn ~= nil, "bouton d'analyse d'inventaire")
click(scanBtn)
mock.advance(1)
local inv = hub.Modules.inventory
check(inv.scanned, "inventaire analysé")
check(inv:count("Bones") == 520, "Bones comptés", inv:count("Bones"))
check(world.log.invokes == 1, "une seule requête envoyée", world.log.invokes)
check(findText(equip, "Ectoplasm : il manque 160") ~= nil, "Skull Guitar : Ectoplasm manquant (250 - 90)")
check(findText(equip, "Magma Ore : il manque 17") ~= nil, "Godhuman : Magma Ore manquant (20 - 3)")
check(findText(equip, "Dark Fragment : il manque 1") ~= nil, "Dark Fragment absent détecté")
check(findText(equip, "Tu possèdes déjà cet objet") ~= nil, "Saber reconnu comme possédé via l'inventaire")
-- anti-spam : une deuxième analyse immédiate est refusée
click(scanBtn)
mock.advance(1)
check(world.log.invokes == 1, "pas de deuxième requête pendant le délai de 15 s", world.log.invokes)
check(diagErrors(hub) == 0, "aucune erreur dans Équipements", lastErrors(hub))

---------------------------------------------------------------------------
section("Races")
---------------------------------------------------------------------------
click(UI.pages.races.navButton)
local racesFrame = UI.pages.races.frame
check(findText(racesFrame, "Ta race : Angel (Skypiea)") ~= nil, "race actuelle affichée")
for id, card in pairs(hub.Modules.races.cards) do
	card.setOpen(true)
end
check(findText(racesFrame, "c'est ta race") ~= nil, "race Angel validée sur les fiches Angel")
check(findText(racesFrame, "tu es Angel") ~= nil, "fiche Human : race différente signalée")
check(findText(racesFrame, "Ectoplasm : il manque 10") ~= nil, "Ghoul : Ectoplasm manquant (100 - 90)")
check(findText(racesFrame, "version non lisible par script") ~= nil, "version de race marquée non vérifiable")
local count = 0
for _ in pairs(hub.Modules.races.cards) do
	count += 1
end
check(count == 8, "8 fiches de race", count)
check(diagErrors(hub) == 0, "aucune erreur dans Races", lastErrors(hub))

---------------------------------------------------------------------------
section("Automatisation (page d'état)")
---------------------------------------------------------------------------
click(UI.pages.automation.navButton)
local auto = UI.pages.automation.frame
for _, name in ipairs({ "Auto Farm", "Auto Boss", "Auto Sword", "Auto Mastery", "Auto Quest" }) do
	check(findText(auto, name) ~= nil, name .. " listé comme non inclus")
end
local hasToggle = false
for _, d in ipairs(auto:GetDescendants()) do
	if d.Name == "Track" then
		hasToggle = true
	end
end
check(not hasToggle, "aucun interrupteur factice sur la page Automatisation")
check(findText(auto, "Aucun script n'est indétectable") ~= nil, "risques de détection expliqués")
check(findText(UI.window, "AUTOMATISATION", "TextLabel") ~= nil, "groupe AUTOMATISATION séparé dans la barre latérale")
check(diagErrors(hub) == 0, "aucune erreur dans Automatisation", lastErrors(hub))

---------------------------------------------------------------------------
section("Recherche")
---------------------------------------------------------------------------
UI.searchBox.Text = "saber"
mock.advance(0.5)
check(UI.current == "search", "la recherche ouvre la page de résultats", UI.current)
local result = findText(UI.pages.search.frame, "Saber   ·   Équipements", "TextButton")
check(result ~= nil, "résultat « Saber » trouvé")
click(result)
mock.advance(0.2)
check(UI.current == "equipment", "clic sur un résultat → page Équipements", UI.current)
check(UI.searchBox.Text == "", "la recherche est vidée")
UI.searchBox.Text = "écouté inexistant zzz"
mock.advance(0.5)
check(findText(UI.pages.search.frame, "Aucun résultat") ~= nil, "message quand aucun résultat")
UI.searchBox.Text = "fragments"
mock.advance(0.5)
check(findText(UI.pages.search.frame, "Fragments", "TextButton") ~= nil, "recherche insensible à la casse")
UI.searchBox.Text = ""
mock.advance(0.3)
check(UI.current ~= "search", "vider la recherche revient à la page précédente", UI.current)
-- 30 recherches successives : la liste des connexions ne doit pas grossir sans limite.
for i = 1, 30 do
	UI.searchBox.Text = (i % 2 == 0) and "race" or "sea"
	mock.advance(0.3)
end
UI.searchBox.Text = ""
mock.advance(0.3)
print("  (info) connexions suivies : " .. #hub.Modules.tasks.connections .. ", actives : " .. hub.Modules.tasks:connectionCount())
check(#hub.Modules.tasks.connections < 600, "connexions des résultats détruits nettoyées", #hub.Modules.tasks.connections)
check(hub.Modules.tasks:connectionCount() < 400, "connexions actives bornées", hub.Modules.tasks:connectionCount())

---------------------------------------------------------------------------
section("Paramètres")
---------------------------------------------------------------------------
click(UI.pages.settings.navButton)
local set = UI.pages.settings.frame
local Config = hub.Modules.config
local notifToggle = findText(set, "Notifications", "TextLabel").Parent
click(notifToggle)
check(Config:get("notifications") == false, "interrupteur Notifications → désactivé")
click(notifToggle)
check(Config:get("notifications") == true, "interrupteur Notifications → réactivé")
local scaleBtn = findText(set, "Normale", "TextButton")
click(scaleBtn)
check(Config:get("uiScale") == 1.15, "taille Grande appliquée", Config:get("uiScale"))
check(UI.scale.Scale == 1.15, "UIScale mis à jour")
click(scaleBtn)
click(scaleBtn)
check(Config:get("uiScale") == 1, "retour à la taille normale", Config:get("uiScale"))
check(world.fs["BloxHub/config.json"] ~= nil, "config sauvegardée dans BloxHub/config.json")
local saved = mock.jsonDecode(world.fs["BloxHub/config.json"])
check(saved.uiScale == 1 and saved.notifications == true, "fichier de config cohérent")
local animToggle = findText(set, "Animations", "TextLabel").Parent
click(animToggle)
check(Config:get("animations") == false, "animations désactivables")
click(animToggle)
check(diagErrors(hub) == 0, "aucune erreur dans Paramètres", lastErrors(hub))

---------------------------------------------------------------------------
section("Réduire / masquer / rouvrir / déplacer")
---------------------------------------------------------------------------
click(UI.pages.dashboard.navButton)
mock.advance(0.5)
local Tasks = hub.Modules.tasks
local minBtn = findText(UI.window.TitleBar, "–", "TextButton")
local closeBtn = findText(UI.window.TitleBar, "×", "TextButton")
click(minBtn)
check(UI.minimized and not UI.body.Visible, "fenêtre réduite")
check(UI.window.Size.Y.Offset == 44, "hauteur réduite à la barre de titre", UI.window.Size.Y.Offset)
mock.advance(3)
check(not Tasks:isRunning("dashboard.refresh"), "rafraîchissement stoppé quand réduit")
click(minBtn)
check(not UI.minimized and UI.body.Visible, "fenêtre restaurée")
check(Tasks:isRunning("dashboard.refresh"), "rafraîchissement relancé à la restauration")
click(closeBtn)
check(not UI.window.Visible and UI.reopenButton.Visible, "fenêtre masquée et bouton ◆ visible")
mock.advance(3)
check(not Tasks:isRunning("dashboard.refresh"), "aucune tâche quand masqué")
click(UI.reopenButton)
check(UI.window.Visible and not UI.reopenButton.Visible, "bouton ◆ rouvre la fenêtre")
-- raccourci clavier
world.uis.InputBegan:Fire(mock.input("Keyboard", nil, "RightShift"), false)
mock.advance(0.1)
check(not UI.window.Visible, "RightShift masque la fenêtre")
world.uis.InputBegan:Fire(mock.input("Keyboard", nil, "RightShift"), true)
mock.advance(0.1)
check(not UI.window.Visible, "touche ignorée si le jeu l'a déjà traitée (chat…)")
world.uis.InputBegan:Fire(mock.input("Keyboard", nil, "RightShift"), false)
mock.advance(0.1)
check(UI.window.Visible, "RightShift réaffiche la fenêtre")
-- déplacement
local before = UI.window.Position
UI.window.TitleBar.InputBegan:Fire(mock.input("MouseButton1", mock.Vector2.new(700, 250)))
world.uis.InputChanged:Fire(mock.input("MouseMovement", mock.Vector2.new(820, 300)))
world.uis.InputEnded:Fire(mock.input("MouseButton1", mock.Vector2.new(820, 300), nil, "End"))
mock.advance(0.1)
check(UI.window.Position.X.Offset == before.X.Offset + 120, "fenêtre déplacée horizontalement", UI.window.Position.X.Offset)
check(Config:get("windowX") == before.X.Offset + 120, "position sauvegardée")
-- déplacement hors écran : la barre de titre reste visible
UI.window.TitleBar.InputBegan:Fire(mock.input("MouseButton1", mock.Vector2.new(0, 0)))
world.uis.InputChanged:Fire(mock.input("MouseMovement", mock.Vector2.new(5000, -5000)))
world.uis.InputEnded:Fire(mock.input("MouseButton1", mock.Vector2.new(5000, -5000), nil, "End"))
mock.advance(0.1)
local pos = UI.window.Position
check(pos.Y.Offset >= -450, "la fenêtre ne sort pas par le haut", pos.Y.Offset)
check(pos.X.Offset <= 1440 / 2 + 660 / 2 - 80, "la fenêtre reste accrochée à l'écran", pos.X.Offset)
check(diagErrors(hub) == 0, "aucune erreur fenêtre", lastErrors(hub))
noScriptErrors("fenêtre")

---------------------------------------------------------------------------
section("Diagnostic et gestion des erreurs")
---------------------------------------------------------------------------
click(UI.pages.diagnostic.navButton)
local diagFrame = UI.pages.diagnostic.frame
check(findText(diagFrame, "MockExec") ~= nil, "nom de l'exécuteur affiché")
check(findText(diagFrame, "lecture / écriture OK") ~= nil, "test réel des fichiers affiché")
local errBtn = findText(diagFrame, "Tester une erreur", "TextButton")
click(errBtn)
check(diagErrors(hub) == 1, "erreur volontaire capturée et journalisée", diagErrors(hub))
check(hub.Running and UI.window.Visible, "le hub survit à l'erreur")
check(findText(diagFrame, "erreur de test volontaire") ~= nil, "erreur visible dans le journal")
click(findText(diagFrame, "Copier le journal", "TextButton"))
check(world.log.clipboard and world.log.clipboard:find("BloxHub", 1, true) ~= nil, "journal copié dans le presse-papiers")
noScriptErrors("diagnostic")

---------------------------------------------------------------------------
section("Performance (60 s simulées sur le Dashboard)")
---------------------------------------------------------------------------
click(UI.pages.dashboard.navButton)
mock.advance(6) -- laisse disparaître les notifications en cours
local snapCalls = 0
local info = hub.Modules.player_info
local origSnap = info.snapshot
info.snapshot = function(...)
	snapCalls += 1
	return origSnap(...)
end
local instBefore = mock.liveInstances()
local connBefore = mock.liveConnections()
local t0 = os.clock()
mock.advance(60)
local cpu = os.clock() - t0
info.snapshot = origSnap
check(snapCalls >= 25 and snapCalls <= 35, "≈30 rafraîchissements pour 60 s à 2 s d'intervalle", snapCalls)
check(#Tasks:list() == 1, "une seule tâche active", #Tasks:list())
check(mock.liveInstances() == instBefore, "aucune fuite d'instances", mock.liveInstances() - instBefore)
check(mock.liveConnections() == connBefore, "aucune fuite de connexions", mock.liveConnections() - connBefore)
print(("  (info) 60 s simulées en %.3f s de CPU, %d instances vivantes, %d connexions"):format(cpu, mock.liveInstances(), mock.liveConnections()))

---------------------------------------------------------------------------
section("Double lancement")
---------------------------------------------------------------------------
local oldHub = hub
local oldGui = UI.gui
local oldTasks = hub.Modules.tasks
world.genv.BloxHubLoading = os.time()
mock.exec(world, SOURCES["loader.lua"], "=loader")
mock.advance(1)
check(world.genv.BloxHub == oldHub, "lancement concurrent refusé pendant un chargement")
world.genv.BloxHubLoading = nil
local _, hub2 = boot({ world = world })
check(hub2 ~= nil and hub2 ~= oldHub, "nouvelle instance créée")
check(not oldHub.Running, "ancienne instance arrêtée")
check(oldTasks.halted and #oldTasks:list() == 0, "anciennes tâches coupées")
check(oldGui.Parent == nil, "ancienne interface détruite")
local guis = 0
for _, c in ipairs(world.hidden:GetChildren()) do
	if c.Name == "BloxHub_UI" then
		guis += 1
	end
end
check(guis == 1, "une seule interface à l'écran", guis)
check(hub2.Modules.config:get("windowX") == Config:get("windowX"), "paramètres conservés après relance")
noScriptErrors("relance")

---------------------------------------------------------------------------
section("Arrêt d'urgence")
---------------------------------------------------------------------------
local UI2 = hub2.Modules.ui
click(UI2.pages.settings.navButton)
local stopBtn = findText(UI2.pages.settings.frame, "Arrêt d'urgence", "TextButton")
local conns = mock.liveConnections()
click(stopBtn)
check(not hub2.Running, "hub arrêté")
check(world.genv.BloxHub == nil, "référence globale nettoyée")
check(UI2.gui.Parent == nil, "interface détruite")
check(#hub2.Modules.tasks:list() == 0, "plus aucune tâche")
check(hub2.Modules.tasks:connectionCount() == 0, "plus aucune connexion du hub")
check(mock.liveConnections() < conns, "connexions réellement libérées", mock.liveConnections() .. " / " .. conns)
mock.advance(10)
check(mock.pending() == 0, "aucun thread en attente après l'arrêt", mock.pending())
noScriptErrors("arrêt")

---------------------------------------------------------------------------
section("Rechargement depuis les paramètres")
---------------------------------------------------------------------------
world.genv.BloxHub = nil
local _, hubR = boot({ world = world })
click(hubR.Modules.ui.pages.settings.navButton)
click(findText(hubR.Modules.ui.pages.settings.frame, "Recharger le hub", "TextButton"))
mock.advance(3)
local hubR2 = world.genv.BloxHub
check(not hubR.Running, "ancienne instance arrêtée au rechargement")
check(hubR2 ~= nil and hubR2 ~= hubR and hubR2.Running, "nouvelle instance après rechargement")
if hubR2 then
	hubR2.Shutdown("test")
end
noScriptErrors("rechargement")

---------------------------------------------------------------------------
section("Module en erreur / désactivé")
---------------------------------------------------------------------------
local brokenSources = sources(BRANCH, function(path, body)
	if path == "src/races.lua" then
		return "return function( -- syntaxe cassée"
	end
	if path == "src/progression.lua" then
		return "return function(Hub) error('panne simulée') end"
	end
	return body
end)
local w3, hub3 = boot({ sources = brokenSources })
check(hub3 and hub3.Running, "le hub démarre malgré deux modules cassés")
check(hub3.ModuleStatus.races == "erreur : syntaxe", "module races en erreur de syntaxe isolé", hub3.ModuleStatus.races)
check(hub3.ModuleStatus.progression == "erreur : initialisation", "module progression en panne isolé", hub3.ModuleStatus.progression)
check(hub3.Modules.ui.pages.races == nil, "pas de page Races")
check(hub3.Modules.ui.pages.equipment ~= nil, "les autres pages restent disponibles")
hub3.Shutdown("test")

local w4 = mock.world({ player = DEFAULT_PLAYER, inventory = INVENTORY, sources = sources(BRANCH) })
w4.fs["BloxHub/config.json"] = '{"modules":{"races":false,"inventory":false},"uiScale":"oops","lastPage":"races"}'
local _, hub4 = boot({ world = w4 })
check(hub4.ModuleStatus.races == "désactivé", "module désactivé dans la config non chargé", hub4.ModuleStatus.races)
check(hub4.Modules.inventory == nil, "lecture d'inventaire désactivable")
check(hub4.Modules.config:get("uiScale") == 1, "valeur de config invalide ignorée")
check(hub4.Modules.ui.current == "dashboard", "page de départ valide malgré une page désactivée", hub4.Modules.ui.current)
click(hub4.Modules.ui.pages.equipment.navButton)
check(findText(hub4.Modules.ui.pages.equipment.frame, "Lecture d'inventaire désactivée") ~= nil, "équipements sans inventaire : message clair")
check(diagErrors(hub4) == 0, "aucune erreur avec modules désactivés", lastErrors(hub4))
hub4.Shutdown("test")
noScriptErrors("modules")

---------------------------------------------------------------------------
section("Compatibilité : exécuteur limité")
---------------------------------------------------------------------------
local w5, hub5 = boot({ files = false, gethui = false, coreguiBlocked = true })
check(hub5 and hub5.Running, "démarre sans fichiers, sans gethui et sans CoreGui")
check(hub5.Modules.ui.gui.Parent == w5.playerGui, "interface repliée sur PlayerGui")
check(hub5.Modules.ui.gui.ResetOnSpawn == false, "l'interface ne disparaît pas à la réapparition")
check(not hub5.Modules.config.persistent, "config en mémoire seulement")
check(not hub5.Modules.compat:has("files"), "fonction fichiers marquée indisponible")
check(diagErrors(hub5) == 0, "aucune erreur en mode limité", lastErrors(hub5))
hub5.Shutdown("test")
noScriptErrors("compat")

---------------------------------------------------------------------------
section("Hors Blox Fruits / données absentes / inventaire bloqué")
---------------------------------------------------------------------------
local w6, hub6 = boot({ placeId = 123, player = false, inventory = "hang" })
check(hub6 and hub6.Running, "démarre hors Blox Fruits")
mock.advance(1)
check(findText(hub6.Modules.ui.window, "Jeu non reconnu") ~= nil, "avertissement « jeu non reconnu »")
for _, id in ipairs({ "progression", "equipment", "races", "diagnostic" }) do
	click(hub6.Modules.ui.pages[id].navButton)
end
for _, card in pairs(hub6.Modules.equipment.cards) do
	card.setOpen(true)
end
local done
hub6.Modules.inventory:scan(function(ok, msg)
	done = { ok, msg }
end)
mock.advance(11)
check(done and done[1] == false, "inventaire : délai de 10 s respecté", done and done[2])
check(not hub6.Modules.tasks:isRunning("inventaire"), "tâche d'inventaire nettoyée après délai")
check(diagErrors(hub6) == 0, "aucune erreur sans données joueur", lastErrors(hub6))
hub6.Shutdown("test")
noScriptErrors("hors jeu")

---------------------------------------------------------------------------
section("Échec réseau")
---------------------------------------------------------------------------
local w7 = mock.world({ player = DEFAULT_PLAYER, sources = {} })
mock.exec(w7, SOURCES["loader.lua"], "=loader")
mock.advance(25)
check(w7.genv.BloxHub == nil, "aucun hub à moitié chargé")
check(w7.genv.BloxHubLoading == nil, "verrou libéré après échec")
check(#w7.log.setcore >= 1, "message d'erreur affiché au joueur")
-- Source personnalisée (fork) via getgenv().BloxHubBase.
local w8 = mock.world({ player = DEFAULT_PLAYER, inventory = INVENTORY, sources = sources("fork") })
w8.genv.BloxHubBase = REPO .. "fork/"
local _, hub8 = boot({ world = w8, wait = 4 })
check(hub8 and hub8.Running, "source personnalisée utilisée (getgenv().BloxHubBase)")
check(hub8 and hub8.Base == REPO .. "fork/", "base personnalisée enregistrée", hub8 and hub8.Base)
if hub8 then
	hub8.Shutdown("test")
end
noScriptErrors("réseau")

---------------------------------------------------------------------------
print(("\n%d tests réussis, %d échoués"):format(passed, failed))
if failed > 0 then
	error("Échecs :\n- " .. table.concat(failures, "\n- "))
end
