-- BloxHub / tasks : gestion des tâches et des connexions.
-- Règles :
--   * une tâche porte un nom unique : la relancer arrête d'abord l'ancienne (jamais de doublon) ;
--   * chaque boucle attend au moins MIN_INTERVAL entre deux exécutions ;
--   * une tâche qui échoue trop souvent s'arrête d'elle-même ;
--   * stopAll / disconnectAll coupent tout immédiatement (arrêt d'urgence).

return function(Hub)
	local Diag = Hub.Modules.diagnostics
	local MIN_INTERVAL = 0.1

	local Tasks = {
		active = {},
		connections = {},
		halted = false,
	}

	local function cancelThread(thread)
		if thread and thread ~= coroutine.running() and coroutine.status(thread) ~= "dead" then
			pcall(task.cancel, thread)
		end
	end

	-- Boucle contrôlée. interval peut être un nombre ou une fonction renvoyant un nombre.
	function Tasks:loop(name, interval, fn, opts)
		opts = opts or {}
		if self.halted then
			return nil
		end
		self:stop(name)
		local token = { name = name, running = true, runs = 0, errors = 0, kind = "boucle" }
		self.active[name] = token
		token.thread = task.spawn(function()
			while token.running and not self.halted do
				local ok = Diag:safe("tâche " .. name, fn)
				token.runs += 1
				if not ok then
					token.errors += 1
					if token.errors >= (opts.maxErrors or 5) then
						Diag:warn(("Tâche « %s » arrêtée après %d erreurs"):format(name, token.errors))
						break
					end
				end
				if not token.running then
					break
				end
				local wait = type(interval) == "function" and interval() or interval
				task.wait(math.max(tonumber(wait) or 1, MIN_INTERVAL))
			end
			token.running = false
			if self.active[name] == token then
				self.active[name] = nil
			end
		end)
		return token
	end

	-- Exécution unique, sans doublon : si une tâche du même nom tourne déjà, on refuse.
	-- callback(ok, result) est appelé à la fin ou après timeout secondes (ok = false, "délai dépassé").
	function Tasks:run(name, fn, timeout, callback)
		if self.halted then
			return false
		end
		if self.active[name] then
			return false
		end
		local token = { name = name, running = true, runs = 0, errors = 0, kind = "unique" }
		self.active[name] = token
		local finished = false
		local function finish(ok, res)
			if finished then
				return
			end
			finished = true
			token.running = false
			if self.active[name] == token then
				self.active[name] = nil
			end
			if callback and not self.halted then
				Diag:safe("retour " .. name, callback, ok, res)
			end
		end
		token.thread = task.spawn(function()
			local ok, res = Diag:safe("tâche " .. name, fn)
			finish(ok, res)
		end)
		if timeout then
			token.timer = task.delay(timeout, function()
				if not finished then
					Diag:warn(("Tâche « %s » : délai de %ds dépassé"):format(name, timeout))
					cancelThread(token.thread)
					finish(false, "délai dépassé")
				end
			end)
		end
		return true
	end

	function Tasks:stop(name)
		local token = self.active[name]
		if not token then
			return
		end
		token.running = false
		self.active[name] = nil
		cancelThread(token.thread)
		cancelThread(token.timer)
	end

	function Tasks:isRunning(name)
		return self.active[name] ~= nil
	end

	function Tasks:list()
		local out = {}
		for name, token in pairs(self.active) do
			table.insert(out, { name = name, runs = token.runs, errors = token.errors, kind = token.kind })
		end
		table.sort(out, function(a, b)
			return a.name < b.name
		end)
		return out
	end

	function Tasks:stopAll()
		for name in pairs(self.active) do
			self:stop(name)
		end
	end

	-- Connexion protégée : le gestionnaire ne peut pas propager d'erreur et sera nettoyé.
	-- Les connexions des éléments détruits (Destroy) sont retirées de la liste régulièrement.
	local sincePrune = 0
	local function prune(list)
		local kept = {}
		for _, c in ipairs(list) do
			if c.Connected then
				table.insert(kept, c)
			end
		end
		return kept
	end

	function Tasks:connect(signal, fn, label)
		local handler = Diag:wrap(label or "connexion", fn)
		local conn = signal:Connect(handler)
		table.insert(self.connections, conn)
		sincePrune += 1
		if sincePrune >= 200 then
			sincePrune = 0
			self.connections = prune(self.connections)
		end
		return conn
	end

	function Tasks:connectionCount()
		local n = 0
		for _, c in ipairs(self.connections) do
			if c.Connected then
				n += 1
			end
		end
		return n
	end

	function Tasks:disconnectAll()
		for _, c in ipairs(self.connections) do
			pcall(function()
				c:Disconnect()
			end)
		end
		table.clear(self.connections)
	end

	-- Arrêt d'urgence : plus aucune tâche ne peut démarrer.
	function Tasks:halt()
		self.halted = true
		self:stopAll()
		self:disconnectAll()
	end

	function Tasks:destroy()
		self:halt()
	end

	return Tasks
end
