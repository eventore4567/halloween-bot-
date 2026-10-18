-- BloxHub / config : paramètres par défaut, chargement et sauvegarde.
-- Sauvegarde dans BloxHub/config.json si l'exécuteur gère les fichiers,
-- sinon les paramètres restent en mémoire pour la session.

return function(Hub)
	local HttpService = game:GetService("HttpService")
	local Compat = Hub.Modules.compat
	local Diag = Hub.Modules.diagnostics
	local genv = (type(getgenv) == "function" and getgenv()) or _G

	local PATH = "BloxHub/config.json"
	local FALLBACK_PATH = "BloxHub_config.json"

	local DEFAULTS = {
		schema = 1,
		modules = {
			inventory = true,
			dashboard = true,
			progression = true,
			equipment = true,
			races = true,
		},
		notifications = true,
		animations = true,
		refreshInterval = 2,
		uiScale = 1,
		toggleKey = "RightShift",
		lastPage = "dashboard",
		windowX = 0,
		windowY = -220,
	}

	local Config = {
		data = nil,
		persistent = Compat:has("files"),
		listeners = {},
	}

	local function deepCopy(t)
		local out = {}
		for k, v in pairs(t) do
			out[k] = type(v) == "table" and deepCopy(v) or v
		end
		return out
	end

	-- Fusion typée : une valeur sauvegardée n'est gardée que si son type correspond au défaut.
	local function merge(defaults, saved)
		local out = deepCopy(defaults)
		if type(saved) ~= "table" then
			return out
		end
		for k, def in pairs(defaults) do
			local v = saved[k]
			if type(def) == "table" then
				out[k] = merge(def, v)
			elseif v ~= nil and type(v) == type(def) then
				out[k] = v
			end
		end
		return out
	end

	local function path()
		return Compat.folder and PATH or FALLBACK_PATH
	end

	function Config:load()
		local saved
		if self.persistent then
			local ok, res = pcall(function()
				if type(isfile) == "function" and not isfile(path()) then
					return nil
				end
				return HttpService:JSONDecode(readfile(path()))
			end)
			if ok then
				saved = res
			else
				Diag:warn("Config illisible, valeurs par défaut utilisées : " .. tostring(res))
			end
		elseif type(genv.BloxHubConfigMemory) == "table" then
			saved = genv.BloxHubConfigMemory
		end
		self.data = merge(DEFAULTS, saved)
		self.data.refreshInterval = math.clamp(self.data.refreshInterval, 1, 10)
		self.data.uiScale = math.clamp(self.data.uiScale, 0.75, 1.25)
	end

	function Config:save()
		if self.persistent then
			local ok, err = pcall(function()
				writefile(path(), HttpService:JSONEncode(self.data))
			end)
			if not ok then
				Diag:warn("Sauvegarde de la config impossible : " .. tostring(err))
			end
			return ok
		end
		genv.BloxHubConfigMemory = deepCopy(self.data)
		return true
	end

	function Config:get(key)
		return self.data[key]
	end

	function Config:set(key, value)
		if self.data[key] == value then
			return
		end
		self.data[key] = value
		self:save()
		for _, fn in ipairs(self.listeners) do
			Diag:safe("config " .. key, fn, key, value)
		end
	end

	function Config:onChange(fn)
		table.insert(self.listeners, fn)
	end

	function Config:moduleEnabled(name)
		local v = self.data.modules[name]
		return v ~= false
	end

	function Config:setModule(name, enabled)
		self.data.modules[name] = enabled and true or false
		self:save()
	end

	function Config:reset()
		self.data = deepCopy(DEFAULTS)
		self:save()
		for _, fn in ipairs(self.listeners) do
			Diag:safe("config reset", fn, "*", nil)
		end
	end

	function Config:destroy()
		table.clear(self.listeners)
	end

	Config:load()
	Diag:info("Config chargée (" .. (Config.persistent and "fichier" or "mémoire seulement") .. ")")
	return Config
end
