-- Roblox FPS Weapon System Framework
-- For game developers building shooter mechanics in Roblox Studio

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local WeaponSystem = {}
WeaponSystem.__index = WeaponSystem

export type WeaponConfig = {
	name: string,
	damage: number,
	fireRate: number,          -- rounds per minute
	spread: number,            -- base spread in degrees
	spreadADS: number,         -- spread while aiming down sights
	recoilVertical: number,    -- vertical kick per shot
	recoilHorizontal: number,  -- horizontal kick range per shot
	recoilRecovery: number,    -- recovery speed (0-1)
	magSize: number,
	reloadTime: number,
	range: number,
	headshotMulti: number,
	fireMode: "auto" | "semi" | "burst",
	burstCount: number?,
}

export type WeaponState = {
	config: WeaponConfig,
	ammo: number,
	isReloading: boolean,
	isADS: boolean,
	lastFireTime: number,
	currentSpread: number,
	recoilOffset: Vector2,
}

function WeaponSystem.new(config: WeaponConfig): WeaponState
	local self = setmetatable({}, WeaponSystem)
	self.config = config
	self.ammo = config.magSize
	self.isReloading = false
	self.isADS = false
	self.lastFireTime = 0
	self.currentSpread = config.spread
	self.recoilOffset = Vector2.zero
	self._connections = {}
	return self
end

function WeaponSystem:canFire(): boolean
	if self.isReloading then return false end
	if self.ammo <= 0 then return false end
	local fireCooldown = 60 / self.config.fireRate
	return (tick() - self.lastFireTime) >= fireCooldown
end

function WeaponSystem:getSpread(): number
	return self.isADS and self.config.spreadADS or self.currentSpread
end

function WeaponSystem:calculateSpreadDirection(aimDirection: Vector3): Vector3
	local spread = self:getSpread()
	local angleX = (math.random() - 0.5) * 2 * math.rad(spread)
	local angleY = (math.random() - 0.5) * 2 * math.rad(spread)
	local cf = CFrame.new(Vector3.zero, aimDirection)
	local rotated = cf * CFrame.Angles(angleX, angleY, 0)
	return rotated.LookVector
end

function WeaponSystem:fire(origin: Vector3, direction: Vector3): RaycastResult?
	if not self:canFire() then return nil end

	self.ammo -= 1
	self.lastFireTime = tick()

	local spreadDir = self:calculateSpreadDirection(direction)

	self:applyRecoil()

	local rayParams = RaycastParams.new()
	rayParams.FilterType = Enum.RaycastFilterType.Exclude
	rayParams.FilterDescendantsInstances = { Players.LocalPlayer.Character }

	local result = workspace:Raycast(origin, spreadDir * self.config.range, rayParams)

	if self.ammo <= 0 then
		self:reload()
	end

	return result
end

function WeaponSystem:applyRecoil()
	local vKick = self.config.recoilVertical
	local hKick = (math.random() - 0.5) * 2 * self.config.recoilHorizontal
	self.recoilOffset += Vector2.new(hKick, -vKick)
	self.currentSpread = math.min(self.currentSpread * 1.15, self.config.spread * 3)
end

function WeaponSystem:update(dt: number)
	self.recoilOffset = self.recoilOffset:Lerp(Vector2.zero, self.config.recoilRecovery * dt * 10)
	self.currentSpread = self.currentSpread + (self.config.spread - self.currentSpread) * dt * 5
end

function WeaponSystem:reload()
	if self.isReloading or self.ammo == self.config.magSize then return end
	self.isReloading = true
	task.delay(self.config.reloadTime, function()
		self.ammo = self.config.magSize
		self.isReloading = false
	end)
end

function WeaponSystem:setADS(aiming: boolean)
	self.isADS = aiming
end

function WeaponSystem:processHit(result: RaycastResult): (number, boolean)
	local part = result.Instance
	local humanoid = part.Parent and part.Parent:FindFirstChildWhichIsA("Humanoid")
	if not humanoid then return 0, false end

	local isHeadshot = part.Name == "Head"
	local damage = self.config.damage
	if isHeadshot then
		damage *= self.config.headshotMulti
	end

	return damage, isHeadshot
end

function WeaponSystem:destroy()
	for _, conn in self._connections do
		conn:Disconnect()
	end
end

-- preset weapon configs for common archetypes
WeaponSystem.Presets = {
	AssaultRifle = {
		name = "Assault Rifle",
		damage = 25,
		fireRate = 600,
		spread = 1.5,
		spreadADS = 0.4,
		recoilVertical = 0.8,
		recoilHorizontal = 0.3,
		recoilRecovery = 0.6,
		magSize = 30,
		reloadTime = 2.2,
		range = 300,
		headshotMulti = 1.5,
		fireMode = "auto",
	},
	SMG = {
		name = "SMG",
		damage = 18,
		fireRate = 900,
		spread = 2.5,
		spreadADS = 1.0,
		recoilVertical = 0.5,
		recoilHorizontal = 0.6,
		recoilRecovery = 0.75,
		magSize = 25,
		reloadTime = 1.8,
		range = 150,
		headshotMulti = 1.4,
		fireMode = "auto",
	},
	Sniper = {
		name = "Sniper",
		damage = 90,
		fireRate = 40,
		spread = 3.0,
		spreadADS = 0.05,
		recoilVertical = 3.0,
		recoilHorizontal = 0.2,
		recoilRecovery = 0.3,
		magSize = 5,
		reloadTime = 3.0,
		range = 1000,
		headshotMulti = 2.5,
		fireMode = "semi",
	},
	Shotgun = {
		name = "Shotgun",
		damage = 12,
		fireRate = 80,
		spread = 6.0,
		spreadADS = 4.0,
		recoilVertical = 2.5,
		recoilHorizontal = 1.0,
		recoilRecovery = 0.4,
		magSize = 8,
		reloadTime = 0.5,
		range = 50,
		headshotMulti = 1.3,
		fireMode = "semi",
	},
}

return WeaponSystem
