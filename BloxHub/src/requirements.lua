-- BloxHub / requirements : évaluation des prérequis (équipements, races, objectifs).
-- Statuts : "ok" (vérifié), "missing" (manquant), "unknown" (non vérifiable par script).
--
-- Types de prérequis :
--   { kind = "level", value = 1500 }
--   { kind = "sea", value = 2 }              -- être dans cette Sea (ou plus loin pour value = "min")
--   { kind = "beli", value = 2000000 }
--   { kind = "fragments", value = 5000 }
--   { kind = "own", names = { "Yama" } }     -- posséder l'un de ces objets
--   { kind = "mastery", name = "Yama", value = 350 }
--   { kind = "material", name = "Bones", value = 500 }
--   { kind = "race", value = "Angel" }
--   { kind = "raceVersion", value = 2 }
--   { kind = "manual", label = "..." }       -- à confirmer soi-même en jeu

return function(Hub)
	local Info = Hub.Modules.player_info
	local fmt = Info.format

	local R = {}

	local function numeric(have, need, label, unit)
		if have == nil then
			return "unknown", label .. " : valeur illisible"
		end
		local detail = ("%s / %s%s"):format(fmt(have), fmt(need), unit or "")
		if have >= need then
			return "ok", detail
		end
		return "missing", detail, ("%s : il manque %s%s"):format(label, fmt(need - have), unit or "")
	end

	local function invHas(inv, name)
		if not inv or not inv.scanned then
			return nil
		end
		return inv:count(name) > 0
	end

	function R.label(req)
		if req.label then
			return req.label
		end
		local k = req.kind
		if k == "level" then
			return "Niveau " .. fmt(req.value)
		elseif k == "sea" then
			return "Être en " .. (Info.SEA_NAMES[req.value] or ("Sea " .. tostring(req.value)))
		elseif k == "beli" then
			return fmt(req.value) .. " Beli"
		elseif k == "fragments" then
			return fmt(req.value) .. " Fragments"
		elseif k == "own" then
			return "Posséder " .. table.concat(req.names, " ou ")
		elseif k == "mastery" then
			return req.name .. " : maîtrise " .. req.value
		elseif k == "material" then
			return fmt(req.value) .. " × " .. req.name
		elseif k == "race" then
			return "Race actuelle : " .. req.value
		elseif k == "raceVersion" then
			return "Race en V" .. req.value
		end
		return tostring(k)
	end

	-- Renvoie status, detail, missingText
	function R.evaluate(req, ctx)
		local k = req.kind
		if k == "level" then
			return numeric(ctx.level, req.value, "Niveau", "")
		elseif k == "beli" then
			return numeric(ctx.beli, req.value, "Beli", "")
		elseif k == "fragments" then
			return numeric(ctx.fragments, req.value, "Fragments", "")
		elseif k == "sea" then
			if ctx.sea == nil then
				return "unknown", "Sea non détectée"
			end
			if ctx.sea == req.value then
				return "ok", "tu y es"
			end
			return "missing", "tu es en " .. (Info.SEA_NAMES[ctx.sea] or "?"), "Aller en " .. (Info.SEA_NAMES[req.value] or "?")
		elseif k == "own" then
			for _, name in ipairs(req.names) do
				if ctx.tools[name] ~= nil then
					return "ok", "dans ton sac"
				end
			end
			local inv = ctx.inventory
			if not inv or not inv.scanned then
				return "unknown", "analyse l'inventaire pour vérifier"
			end
			for _, name in ipairs(req.names) do
				if invHas(inv, name) then
					return "ok", "dans l'inventaire"
				end
			end
			return "missing", "absent de l'inventaire", "Obtenir " .. table.concat(req.names, " ou ")
		elseif k == "mastery" then
			local m = ctx.tools[req.name]
			if (m == nil or m == 0) and ctx.inventory and ctx.inventory.scanned then
				m = ctx.inventory:mastery(req.name)
			end
			if m == nil or m == 0 then
				return "unknown", "équipe ou range l'objet dans ton sac pour lire sa maîtrise"
			end
			return numeric(m, req.value, req.name .. " (maîtrise)", "")
		elseif k == "material" then
			local inv = ctx.inventory
			if not inv or not inv.scanned then
				return "unknown", "analyse l'inventaire pour vérifier"
			end
			return numeric(inv:count(req.name), req.value, req.name, "")
		elseif k == "race" then
			if ctx.race == nil then
				return "unknown", "race non détectée"
			end
			if ctx.race == req.value then
				return "ok", "c'est ta race"
			end
			return "missing", "tu es " .. tostring(ctx.race), "Avoir la race " .. req.value
		elseif k == "raceVersion" then
			if ctx.raceVersion == nil then
				return "unknown", "version non lisible par script : vérifie en jeu"
			end
			if ctx.raceVersion >= req.value then
				return "ok", "V" .. ctx.raceVersion
			end
			return "missing", "V" .. ctx.raceVersion, "Passer ta race en V" .. req.value
		end
		return "unknown", "à confirmer en jeu"
	end

	-- Résumé d'une liste de prérequis.
	function R.summarize(reqs, ctx)
		local sum = { ok = 0, missing = 0, unknown = 0, total = #reqs, rows = {}, missingList = {} }
		for _, req in ipairs(reqs) do
			local status, detail, missingText = R.evaluate(req, ctx)
			sum[status] += 1
			table.insert(sum.rows, { req = req, status = status, label = R.label(req), detail = detail })
			if status == "missing" and missingText then
				table.insert(sum.missingList, missingText)
			end
		end
		local checkable = sum.ok + sum.missing
		sum.ratio = sum.total > 0 and (sum.ok / sum.total) or 1
		sum.checkable = checkable
		return sum
	end

	-- Construit le contenu détaillé d'une fiche (équipement ou race) dans body.
	function R.render(body, entry, ctx)
		local UI = Hub.Modules.ui
		local c = UI.c
		local sum = R.summarize(entry.reqs or {}, ctx)

		if entry.summary then
			c.label(body, entry.summary, { muted = true })
		end

		local owned = false
		if entry.owned then
			local st = R.evaluate({ kind = "own", names = entry.owned }, ctx)
			owned = st == "ok"
			if owned then
				c.status(body, "ok", "Tu possèdes déjà cet objet")
			end
		end

		if #(entry.reqs or {}) > 0 then
			c.progress(body, "Progression", sum.ratio, ("%d / %d vérifiés"):format(sum.ok, sum.total))
			c.label(body, "Prérequis", { bold = true, size = 12 })
			for _, row in ipairs(sum.rows) do
				c.status(body, row.status, row.label, row.detail)
			end
		end

		if entry.steps and #entry.steps > 0 then
			c.label(body, "Étapes", { bold = true, size = 12 })
			for i, step in ipairs(entry.steps) do
				c.label(body, ("%d. %s"):format(i, step))
			end
		end

		c.label(body, "Ressources manquantes", { bold = true, size = 12 })
		if #sum.missingList == 0 then
			if sum.unknown > 0 then
				c.label(body, "Rien de manquant parmi ce qui est vérifiable. Les points « ? » sont à confirmer en jeu.", { muted = true })
			else
				c.label(body, "Aucune : tout est réuni.", { color = UI.Theme.ok })
			end
		else
			for _, text in ipairs(sum.missingList) do
				c.status(body, "missing", text)
			end
		end

		if entry.warning then
			c.status(body, "warn", entry.warning)
		end
		return sum, owned
	end

	return R
end
