-- BloxHub / player_info : lecture (seule) des informations du joueur.
-- Toutes les lectures sont protégées : une valeur absente donne nil, jamais une erreur.

return function(Hub)
	local Players = game:GetService("Players")
	local Diag = Hub.Modules.diagnostics

	local LocalPlayer = Players.LocalPlayer

	local SEA_BY_PLACE = {
		[2753915549] = 1,
		[4442272183] = 2,
		[7449423635] = 3,
	}
	local SEA_NAMES = { "First Sea", "Second Sea", "Third Sea" }

	-- Noms internes possibles → nom affiché / clé utilisée par les guides.
	local RACES = {
		Human = { key = "Human", name = "Human" },
		Skypiea = { key = "Angel", name = "Angel (Skypiea)" },
		Angel = { key = "Angel", name = "Angel" },
		Fishman = { key = "Shark", name = "Shark (Fishman)" },
		Shark = { key = "Shark", name = "Shark" },
		Mink = { key = "Mink", name = "Mink (Rabbit)" },
		Rabbit = { key = "Mink", name = "Rabbit (Mink)" },
		Cyborg = { key = "Cyborg", name = "Cyborg" },
		Ghoul = { key = "Ghoul", name = "Ghoul" },
		Draco = { key = "Draco", name = "Draco" },
	}

	local Info = { SEA_NAMES = SEA_NAMES }

	local function readValue(parent, name)
		if not parent then
			return nil
		end
		local ok, v = pcall(function()
			local child = parent:FindFirstChild(name)
			return child and child.Value
		end)
		if ok then
			return v
		end
		return nil
	end
	Info.readValue = readValue

	function Info:sea()
		return SEA_BY_PLACE[game.PlaceId]
	end

	function Info:isBloxFruits()
		return SEA_BY_PLACE[game.PlaceId] ~= nil
	end

	function Info:data()
		return LocalPlayer:FindFirstChild("Data")
	end

	-- Liste des outils du sac et du personnage, avec maîtrise si le jeu l'expose.
	function Info:tools()
		local out = {}
		local function scan(container, equipped)
			if not container then
				return
			end
			for _, t in ipairs(container:GetChildren()) do
				if t:IsA("Tool") then
					local mastery = tonumber(readValue(t, "Level"))
					local tip = ""
					pcall(function()
						tip = t.ToolTip
					end)
					table.insert(out, {
						name = t.Name,
						mastery = mastery,
						kind = (tip ~= "" and tip) or nil,
						equipped = equipped,
					})
				end
			end
		end
		scan(LocalPlayer.Character, true)
		scan(LocalPlayer:FindFirstChildOfClass("Backpack"), false)
		return out
	end

	function Info:snapshot()
		local data = self:data()
		local s = {
			dataReady = data ~= nil,
			sea = self:sea(),
			placeId = game.PlaceId,
		}
		s.seaName = s.sea and SEA_NAMES[s.sea] or nil
		s.level = tonumber(readValue(data, "Level"))
		s.beli = tonumber(readValue(data, "Beli"))
		s.fragments = tonumber(readValue(data, "Fragments"))
		s.fruit = readValue(data, "DevilFruit")
		if s.fruit == "" then
			s.fruit = nil
		end

		local raceRaw = readValue(data, "Race")
		if type(raceRaw) == "string" and raceRaw ~= "" then
			local r = RACES[raceRaw]
			s.raceKey = r and r.key or raceRaw
			s.race = r and r.name or raceRaw
			-- V2 : certains serveurs exposent un indicateur « Evolved » sous Data.Race.
			local raceObj = data and data:FindFirstChild("Race")
			local evolved = raceObj and readValue(raceObj, "Evolved")
			if evolved == true then
				s.raceVersion = 2
			end
		end

		local char = LocalPlayer.Character
		local tool = char and char:FindFirstChildOfClass("Tool")
		if tool then
			s.weapon = tool.Name
			s.weaponMastery = tonumber(readValue(tool, "Level"))
		end
		return s
	end

	-- Contexte utilisé par le module requirements.
	function Info:context()
		local s = self:snapshot()
		local tools = {}
		for _, t in ipairs(self:tools()) do
			local prev = tools[t.name]
			tools[t.name] = math.max(prev or 0, t.mastery or 0)
		end
		return {
			snap = s,
			level = s.level,
			beli = s.beli,
			fragments = s.fragments,
			sea = s.sea,
			race = s.raceKey,
			raceVersion = s.raceVersion,
			tools = tools,
			inventory = Hub.Modules.inventory,
		}
	end

	function Info.format(n)
		if type(n) ~= "number" then
			return "—"
		end
		local s = tostring(math.floor(n))
		local neg = s:sub(1, 1) == "-"
		if neg then
			s = s:sub(2)
		end
		local out = s:reverse():gsub("(%d%d%d)", "%1 "):reverse():gsub("^ ", "")
		return (neg and "-" or "") .. out
	end

	if not Info:isBloxFruits() then
		Diag:warn(("Jeu non reconnu (PlaceId %s) : les infos Blox Fruits peuvent manquer"):format(tostring(game.PlaceId)))
	end

	return Info
end
