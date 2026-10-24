-- Server-side Hit Registration System
-- Validates client fire requests, prevents exploits

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local HitRegistration = {}
HitRegistration.__index = HitRegistration

export type HitValidationConfig = {
	maxFireRate: number,       -- max RPM allowed per weapon
	maxRange: number,          -- max raycast distance
	positionTolerance: number, -- studs of allowed position mismatch
	angleTolerance: number,    -- degrees of allowed aim angle mismatch
	maxPendingHits: number,    -- rate limit on hit claims per second
	lagCompensationMs: number, -- max rewind for lag compensation
}

local DEFAULT_VALIDATION: HitValidationConfig = {
	maxFireRate = 1200,
	maxRange = 1500,
	positionTolerance = 10,
	angleTolerance = 15,
	maxPendingHits = 30,
	lagCompensationMs = 200,
}

function HitRegistration.new(config: HitValidationConfig?)
	local self = setmetatable({}, HitRegistration)
	self.config = config or DEFAULT_VALIDATION
	self.playerData = {} -- per-player tracking
	self.positionHistory = {} -- for lag compensation
	self._connections = {}
	return self
end

function HitRegistration:trackPlayer(player: Player)
	self.playerData[player] = {
		lastFireTime = 0,
		hitCount = 0,
		hitResetTime = 0,
		suspicionScore = 0,
		weaponFireRates = {},
	}
	self.positionHistory[player] = {}

	table.insert(self._connections, RunService.Heartbeat:Connect(function()
		self:recordPosition(player)
	end))
end

function HitRegistration:recordPosition(player: Player)
	local char = player.Character
	if not char then return end
	local root = char:FindFirstChild("HumanoidRootPart")
	if not root then return end

	local history = self.positionHistory[player]
	if not history then return end

	table.insert(history, {
		time = tick(),
		position = root.Position,
		cframe = root.CFrame,
	})

	while #history > 60 do
		table.remove(history, 1)
	end
end

function HitRegistration:getHistoricalPosition(player: Player, timestamp: number): CFrame?
	local history = self.positionHistory[player]
	if not history or #history == 0 then return nil end

	local best = nil
	local bestDiff = math.huge
	for _, entry in history do
		local diff = math.abs(entry.time - timestamp)
		if diff < bestDiff then
			bestDiff = diff
			best = entry
		end
	end

	return best and best.cframe or nil
end

export type FireRequest = {
	player: Player,
	origin: Vector3,
	direction: Vector3,
	weaponId: string,
	timestamp: number,
	targetPart: BasePart?,
}

export type ValidationResult = {
	valid: boolean,
	reason: string?,
	damage: number,
	headshot: boolean,
	hitPlayer: Player?,
}

function HitRegistration:validateFire(request: FireRequest): ValidationResult
	local data = self.playerData[request.player]
	if not data then
		return { valid = false, reason = "untracked_player", damage = 0, headshot = false }
	end

	if not self:validateFireRate(request, data) then
		data.suspicionScore += 5
		return { valid = false, reason = "fire_rate_exceeded", damage = 0, headshot = false }
	end

	if not self:validateOrigin(request) then
		data.suspicionScore += 10
		return { valid = false, reason = "invalid_origin", damage = 0, headshot = false }
	end

	if not self:validateHitRate(data) then
		data.suspicionScore += 3
		return { valid = false, reason = "hit_rate_exceeded", damage = 0, headshot = false }
	end

	local result = self:performRaycast(request)

	if data.suspicionScore > 50 then
		self:flagPlayer(request.player, data.suspicionScore)
	end

	data.lastFireTime = tick()
	return result
end

function HitRegistration:validateFireRate(request: FireRequest, data): boolean
	local now = tick()
	local minInterval = 60 / self.config.maxFireRate
	return (now - data.lastFireTime) >= (minInterval * 0.9) -- 10% tolerance for network jitter
end

function HitRegistration:validateOrigin(request: FireRequest): boolean
	local char = request.player.Character
	if not char then return false end
	local root = char:FindFirstChild("HumanoidRootPart")
	if not root then return false end

	local distance = (request.origin - root.Position).Magnitude
	return distance <= self.config.positionTolerance
end

function HitRegistration:validateHitRate(data): boolean
	local now = tick()
	if now - data.hitResetTime > 1 then
		data.hitCount = 0
		data.hitResetTime = now
	end
	data.hitCount += 1
	return data.hitCount <= self.config.maxPendingHits
end

function HitRegistration:performRaycast(request: FireRequest): ValidationResult
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { request.player.Character }

	local result = workspace:Raycast(
		request.origin,
		request.direction.Unit * self.config.maxRange,
		params
	)

	if not result then
		return { valid = true, reason = "miss", damage = 0, headshot = false }
	end

	local hitModel = result.Instance:FindFirstAncestorWhichIsA("Model")
	local hitPlayer = hitModel and Players:GetPlayerFromCharacter(hitModel)

	if not hitPlayer then
		return { valid = true, reason = "environment_hit", damage = 0, headshot = false }
	end

	if hitPlayer.Team == request.player.Team and hitPlayer.Team ~= nil then
		return { valid = true, reason = "friendly_fire", damage = 0, headshot = false }
	end

	local isHeadshot = result.Instance.Name == "Head"

	if self.config.lagCompensationMs > 0 then
		local rewindTime = request.timestamp - (self.config.lagCompensationMs / 1000)
		local historicalCF = self:getHistoricalPosition(hitPlayer, rewindTime)
		if historicalCF then
			local historicalHead = historicalCF.Position + Vector3.new(0, 1.5, 0)
			local distToHit = (result.Position - historicalHead).Magnitude
			if distToHit > self.config.positionTolerance * 2 then
				return { valid = false, reason = "lag_comp_mismatch", damage = 0, headshot = false }
			end
		end
	end

	return {
		valid = true,
		reason = "hit",
		damage = 0, -- caller applies weapon-specific damage
		headshot = isHeadshot,
		hitPlayer = hitPlayer,
	}
end

function HitRegistration:flagPlayer(player: Player, score: number)
	warn(`[HitReg] Player {player.Name} flagged with suspicion score {score}`)
	-- integrate with your moderation system here
end

function HitRegistration:cleanup(player: Player)
	self.playerData[player] = nil
	self.positionHistory[player] = nil
end

function HitRegistration:destroy()
	for _, conn in self._connections do
		conn:Disconnect()
	end
	self.playerData = {}
	self.positionHistory = {}
end

return HitRegistration
