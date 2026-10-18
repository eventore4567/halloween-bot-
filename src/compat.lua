-- BloxHub / compat : détection des API de l'exécuteur.
-- Chaque fonctionnalité dépendante d'une API non standard passe par ce module :
-- si l'API est absente ou ne fonctionne pas, la fonctionnalité est désactivée proprement.

return function(Hub)
	local Compat = {
		checks = {},
		features = {},
		executor = "inconnu",
	}

	local function isFn(v)
		return type(v) == "function"
	end

	local function add(id, label, ok, detail)
		table.insert(Compat.checks, { id = id, label = label, ok = ok and true or false, detail = detail })
		Compat.features[id] = ok and true or false
	end

	-- Nom de l'exécuteur (purement informatif).
	if isFn(identifyexecutor) then
		local ok, name, ver = pcall(identifyexecutor)
		if ok and name then
			Compat.executor = tostring(name) .. (ver and (" " .. tostring(ver)) or "")
		end
	elseif isFn(getexecutorname) then
		local ok, name = pcall(getexecutorname)
		if ok and name then
			Compat.executor = tostring(name)
		end
	end

	add("loadstring", "loadstring", isFn(loadstring))
	add("httpget", "game:HttpGet", true, "utilisé pour charger le hub")
	add("getgenv", "getgenv", isFn(getgenv))

	-- Conteneur d'interface protégé.
	local hui
	if isFn(gethui) then
		local ok, res = pcall(gethui)
		if ok and typeof(res) == "Instance" then
			hui = res
		end
	end
	Compat.hui = hui
	add("gethui", "gethui", hui ~= nil)

	-- Fichiers : on teste réellement l'écriture puis la relecture.
	local filesOk, filesDetail = false, "API absente"
	if isFn(writefile) and isFn(readfile) then
		local ok, err = pcall(function()
			if isFn(isfolder) and isFn(makefolder) and not isfolder("BloxHub") then
				makefolder("BloxHub")
			end
			local path = (isFn(isfolder) and isfolder("BloxHub")) and "BloxHub/.compat_test" or "BloxHub_compat_test.txt"
			writefile(path, "ok")
			local back = readfile(path)
			if isFn(delfile) then
				pcall(delfile, path)
			end
			assert(back == "ok", "relecture différente")
		end)
		filesOk, filesDetail = ok, ok and "lecture / écriture OK" or tostring(err)
	end
	add("files", "Fichiers (sauvegarde config)", filesOk, filesDetail)
	Compat.folder = filesOk and isFn(isfolder) and isfolder("BloxHub")

	-- Presse-papiers : on vérifie seulement la présence (ne jamais écraser le presse-papiers sans action).
	local clip = (isFn(setclipboard) and setclipboard) or (isFn(toclipboard) and toclipboard) or nil
	Compat.setclipboard = clip
	add("clipboard", "Presse-papiers", clip ~= nil)

	add("taskcancel", "task.cancel", type(task) == "table" and isFn(task.cancel))

	local okCore = pcall(function()
		return game:GetService("CoreGui"):GetChildren()
	end)
	add("coregui", "Accès CoreGui", okCore)

	function Compat:copy(text)
		if not self.setclipboard then
			return false
		end
		return (pcall(self.setclipboard, text))
	end

	function Compat:has(id)
		return self.features[id] == true
	end

	return Compat
end
