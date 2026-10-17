-- BloxHub / inventory : lecture de l'inventaire, uniquement à la demande.
-- Utilise la même requête en lecture seule que l'inventaire du jeu ("getInventory").
-- Rien n'est modifié côté serveur. Délai maximal : 10 s. Pas plus d'une analyse toutes les 15 s.

return function(Hub)
	local ReplicatedStorage = game:GetService("ReplicatedStorage")
	local Diag = Hub.Modules.diagnostics
	local Tasks = Hub.Modules.tasks

	local TIMEOUT = 10
	local COOLDOWN = 15
	local now = type(tick) == "function" and tick or os.clock

	local Inventory = {
		scanned = false,
		items = {},
		lastScan = nil,
		lastError = nil,
		listeners = {},
	}

	local function remote()
		local remotes = ReplicatedStorage:FindFirstChild("Remotes")
		local comm = remotes and remotes:FindFirstChild("CommF_")
		if comm and comm:IsA("RemoteFunction") then
			return comm
		end
		return nil
	end

	function Inventory:available()
		return remote() ~= nil
	end

	local function parse(raw)
		local items = {}
		if type(raw) ~= "table" then
			return nil
		end
		for key, entry in pairs(raw) do
			if type(entry) == "table" then
				local name = entry.Name or entry.name
				if type(name) == "string" then
					local count = tonumber(entry.Count or entry.count) or 1
					local mastery = tonumber(entry.Mastery or entry.mastery)
					local prev = items[name]
					items[name] = {
						count = (prev and prev.count or 0) + count,
						mastery = math.max(prev and prev.mastery or 0, mastery or 0),
						kind = entry.Type or entry.type,
					}
				end
			elseif type(key) == "string" and type(entry) == "number" then
				items[key] = { count = entry, mastery = 0 }
			end
		end
		return items
	end
	Inventory.parse = parse

	function Inventory:count(name)
		local it = self.items[name]
		return it and it.count or 0
	end

	function Inventory:mastery(name)
		local it = self.items[name]
		return it and it.mastery or nil
	end

	function Inventory:onUpdate(fn)
		table.insert(self.listeners, fn)
	end

	-- callback(ok, message)
	function Inventory:scan(callback)
		local function done(ok, msg)
			if callback then
				Diag:safe("retour inventaire", callback, ok, msg)
			end
		end
		if self.lastScan and now() - self.lastScan < COOLDOWN then
			done(false, ("Patiente %ds entre deux analyses."):format(math.ceil(COOLDOWN - (now() - self.lastScan))))
			return
		end
		local comm = remote()
		if not comm then
			self.lastError = "requête d'inventaire introuvable dans ce jeu"
			done(false, "Lecture de l'inventaire indisponible ici.")
			return
		end
		self.lastScan = now()
		local started = Tasks:run("inventaire", function()
			return comm:InvokeServer("getInventory")
		end, TIMEOUT, function(ok, res)
			if not ok then
				self.lastError = tostring(res)
				done(false, "Lecture impossible : " .. tostring(res))
				return
			end
			local items = parse(res)
			if not items then
				self.lastError = "réponse inattendue"
				done(false, "Réponse d'inventaire inattendue.")
				return
			end
			self.items = items
			self.scanned = true
			self.lastError = nil
			local n = 0
			for _ in pairs(items) do
				n += 1
			end
			Diag:info(("Inventaire lu : %d objets"):format(n))
			for _, fn in ipairs(self.listeners) do
				Diag:safe("inventaire listener", fn)
			end
			done(true, ("%d objets lus."):format(n))
		end)
		if not started then
			done(false, "Analyse déjà en cours.")
		end
	end

	function Inventory:destroy()
		table.clear(self.listeners)
	end

	return Inventory
end
