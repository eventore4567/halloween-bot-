-- BloxHub / diagnostics : journal technique et exécution protégée.

return function(Hub)
	local MAX_ENTRIES = 300

	local Diag = {
		entries = {},
		counts = { INFO = 0, WARN = 0, ERROR = 0 },
		listeners = {},
	}

	local function stamp()
		local ok, s = pcall(os.date, "%H:%M:%S")
		return ok and s or "--:--:--"
	end

	function Diag:log(level, msg)
		msg = tostring(msg)
		local entry = { t = stamp(), level = level, msg = msg }
		table.insert(self.entries, entry)
		if #self.entries > MAX_ENTRIES then
			table.remove(self.entries, 1)
		end
		self.counts[level] = (self.counts[level] or 0) + 1
		if level ~= "INFO" then
			warn(("[BloxHub][%s] %s"):format(level, msg))
		end
		for _, fn in ipairs(self.listeners) do
			pcall(fn, entry)
		end
	end

	function Diag:info(msg)
		self:log("INFO", msg)
	end

	function Diag:warn(msg)
		self:log("WARN", msg)
	end

	function Diag:error(msg)
		self:log("ERROR", msg)
	end

	-- Exécute fn dans un xpcall ; en cas d'erreur, l'erreur est journalisée avec sa pile.
	function Diag:safe(label, fn, ...)
		local args = table.pack(...)
		local ok, res = xpcall(function()
			return fn(table.unpack(args, 1, args.n))
		end, debug.traceback)
		if not ok then
			self:error(("%s : %s"):format(tostring(label), tostring(res)))
		end
		return ok, res
	end

	-- Enveloppe une fonction pour qu'elle ne puisse jamais propager d'erreur.
	function Diag:wrap(label, fn)
		return function(...)
			local _, res = self:safe(label, fn, ...)
			return res
		end
	end

	function Diag:onEntry(fn)
		table.insert(self.listeners, fn)
		return function()
			for i, f in ipairs(self.listeners) do
				if f == fn then
					table.remove(self.listeners, i)
					break
				end
			end
		end
	end

	function Diag:recent(n)
		local out = {}
		local first = math.max(1, #self.entries - (n or 50) + 1)
		for i = first, #self.entries do
			table.insert(out, self.entries[i])
		end
		return out
	end

	function Diag:dump()
		local lines = { ("BloxHub %s — journal technique"):format(Hub.Version) }
		for _, e in ipairs(self.entries) do
			table.insert(lines, ("[%s][%s] %s"):format(e.t, e.level, e.msg))
		end
		return table.concat(lines, "\n")
	end

	function Diag:memoryKB()
		local ok, kb = pcall(gcinfo)
		if ok and type(kb) == "number" then
			return kb
		end
		ok, kb = pcall(collectgarbage, "count")
		return ok and kb or nil
	end

	function Diag:destroy()
		table.clear(self.listeners)
	end

	Diag:info(("Démarrage de BloxHub %s"):format(Hub.Version))
	return Diag
end
