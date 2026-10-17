--[[
	BloxHub — chargeur
	Hub d'informations et de progression pour Blox Fruits (interface en français).

	Lancement :
		loadstring(game:HttpGet("https://raw.githubusercontent.com/eventore4567/halloween-bot-/refs/heads/claude/eloquent-einstein-ppayu4/BloxHub/loader.lua"))()

	Le chargeur :
	  1. empêche un double lancement (l'ancienne instance est arrêtée proprement) ;
	  2. télécharge les modules en parallèle avec un délai maximal ;
	  3. initialise chaque module dans un pcall : un module en erreur est désactivé
	     sans faire tomber le reste du hub ;
	  4. n'exécute aucune automatisation de jeu : le hub lit et affiche des informations.
]]

local VERSION = "1.0.0"
local REPO = "https://raw.githubusercontent.com/eventore4567/halloween-bot-/refs/heads/"
local REFS = { "claude/eloquent-einstein-ppayu4", "main" }
local DIR = "/BloxHub/"
local FETCH_TIMEOUT = 20
local GAME_LOAD_TIMEOUT = 30

-- Ordre d'initialisation. Les modules « core » sont indispensables ; les autres
-- peuvent être désactivés dans les paramètres ou échouer sans bloquer le hub.
local MODULES = {
	{ name = "compat", core = true },
	{ name = "diagnostics", core = true },
	{ name = "tasks", core = true },
	{ name = "config", core = true },
	{ name = "ui", core = true },
	{ name = "notifications", core = true },
	{ name = "player_info", core = true },
	{ name = "requirements", core = true },
	{ name = "inventory" },
	{ name = "dashboard" },
	{ name = "progression" },
	{ name = "equipment" },
	{ name = "races" },
	{ name = "settings", core = true },
}

local genv = (type(getgenv) == "function" and getgenv()) or _G

local function report(msg)
	warn("[BloxHub] " .. msg)
	pcall(function()
		game:GetService("StarterGui"):SetCore("SendNotification", {
			Title = "BloxHub",
			Text = msg,
			Duration = 8,
		})
	end)
end

-- Verrou anti double exécution simultanée (un verrou de plus de 60 s est ignoré).
if genv.BloxHubLoading and (os.time() - genv.BloxHubLoading) < 60 then
	report("Chargement déjà en cours, patiente quelques secondes.")
	return
end
genv.BloxHubLoading = os.time()

local function unlock()
	genv.BloxHubLoading = nil
end

-- Une instance tourne déjà : on l'arrête proprement avant de relancer.
if type(genv.BloxHub) == "table" and type(genv.BloxHub.Shutdown) == "function" then
	pcall(genv.BloxHub.Shutdown, "relance")
	genv.BloxHub = nil
end

-- Attente bornée du chargement du jeu et du joueur local.
do
	local waited = 0
	while not game:IsLoaded() and waited < GAME_LOAD_TIMEOUT do
		waited += task.wait(0.25)
	end
	local Players = game:GetService("Players")
	while not Players.LocalPlayer and waited < GAME_LOAD_TIMEOUT do
		waited += task.wait(0.25)
	end
	if not Players.LocalPlayer then
		unlock()
		report("Joueur local introuvable : chargement annulé.")
		return
	end
end

if type(loadstring) ~= "function" then
	unlock()
	report("Ton exécuteur ne fournit pas loadstring : impossible de charger les modules.")
	return
end

local function fetchAll(base)
	local results, pending = {}, #MODULES
	for _, def in ipairs(MODULES) do
		task.spawn(function()
			local ok, body = pcall(function()
				return game:HttpGet(base .. "src/" .. def.name .. ".lua")
			end)
			if ok and type(body) == "string" and #body > 0 and not body:match("^%s*404") then
				results[def.name] = body
			else
				results[def.name] = false
			end
			pending -= 1
		end)
	end
	local waited = 0
	while pending > 0 and waited < FETCH_TIMEOUT do
		waited += task.wait(0.05)
	end
	return results, pending
end

-- Choix de la source : surcharge manuelle, puis branche de développement, puis main.
local bases = {}
if type(genv.BloxHubBase) == "string" then
	table.insert(bases, genv.BloxHubBase)
end
for _, ref in ipairs(REFS) do
	table.insert(bases, REPO .. ref .. DIR)
end

local sources, base
for _, candidate in ipairs(bases) do
	local res = fetchAll(candidate)
	if res.compat and res.ui then
		sources, base = res, candidate
		break
	end
end

if not sources then
	unlock()
	report("Impossible de télécharger les modules (réseau ou GitHub indisponible).")
	return
end

local Hub = {
	Version = VERSION,
	Base = base,
	LoaderUrl = base .. "loader.lua",
	Modules = {},
	ModuleStatus = {},
	ModuleOrder = {},
	Running = true,
	StartedAt = os.time(),
}
genv.BloxHub = Hub

function Hub.Shutdown(reason)
	if not Hub.Running then
		return
	end
	Hub.Running = false
	local t = Hub.Modules.tasks
	if t then
		pcall(t.stopAll, t)
		pcall(t.disconnectAll, t)
	end
	for i = #Hub.ModuleOrder, 1, -1 do
		local mod = Hub.Modules[Hub.ModuleOrder[i]]
		if type(mod) == "table" and type(mod.destroy) == "function" then
			pcall(mod.destroy, mod)
		end
	end
	if Hub.Modules.diagnostics then
		pcall(Hub.Modules.diagnostics.info, Hub.Modules.diagnostics, "Hub arrêté (" .. tostring(reason or "manuel") .. ")")
	end
	if genv.BloxHub == Hub then
		genv.BloxHub = nil
	end
end

function Hub.Reload()
	local url = Hub.LoaderUrl
	Hub.Shutdown("rechargement")
	task.delay(0.2, function()
		local ok, err = pcall(function()
			loadstring(game:HttpGet(url))()
		end)
		if not ok then
			report("Rechargement impossible : " .. tostring(err))
		end
	end)
end

-- Raccourci de notification utilisable par tous les modules, même avant l'UI.
function Hub.notify(title, text, kind, duration)
	local n = Hub.Modules.notifications
	if n and n.push then
		n:push(title, text, kind, duration)
	end
end

function Hub.isEnabled(name)
	local cfg = Hub.Modules.config
	if not cfg then
		return true
	end
	return cfg:moduleEnabled(name)
end

local function initModule(def)
	local name = def.name
	if not def.core and not Hub.isEnabled(name) then
		Hub.ModuleStatus[name] = "désactivé"
		return true
	end
	local src = sources[name]
	if not src then
		Hub.ModuleStatus[name] = "erreur : téléchargement"
		return false, "téléchargement impossible"
	end
	local chunk, cerr = loadstring(src, "=BloxHub/" .. name)
	if not chunk then
		Hub.ModuleStatus[name] = "erreur : syntaxe"
		return false, cerr
	end
	local ok, factory = pcall(chunk)
	if not ok or type(factory) ~= "function" then
		Hub.ModuleStatus[name] = "erreur : format"
		return false, ok and "le module ne renvoie pas de fonction" or factory
	end
	local ok2, mod = xpcall(factory, debug.traceback, Hub)
	if not ok2 then
		Hub.ModuleStatus[name] = "erreur : initialisation"
		return false, mod
	end
	Hub.Modules[name] = mod
	table.insert(Hub.ModuleOrder, name)
	Hub.ModuleStatus[name] = "actif"
	return true
end

for _, def in ipairs(MODULES) do
	local ok, err = initModule(def)
	if not ok then
		local diag = Hub.Modules.diagnostics
		if diag then
			diag:error("Module " .. def.name .. " : " .. tostring(err))
		end
		if def.core then
			report("Module essentiel « " .. def.name .. " » en échec : " .. tostring(err))
			Hub.Shutdown("échec du module " .. def.name)
			unlock()
			return
		end
	end
end

local ui = Hub.Modules.ui
local okStart, errStart = pcall(ui.start, ui)
unlock()
if not okStart then
	report("Ouverture de l'interface impossible : " .. tostring(errStart))
	Hub.Shutdown("échec de l'interface")
	return
end

Hub.Modules.diagnostics:info(("BloxHub %s prêt (source : %s)"):format(VERSION, base))
Hub.notify("BloxHub " .. VERSION, "Prêt. RightShift ou le bouton ◆ pour afficher / masquer.", "success", 5)

return Hub
