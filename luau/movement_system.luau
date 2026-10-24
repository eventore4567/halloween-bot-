-- Roblox Movement System Framework
-- Sliding, wall-running, dashing, mantling for FPS/TPS games

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local MovementSystem = {}
MovementSystem.__index = MovementSystem

export type MovementConfig = {
	walkSpeed: number,
	sprintSpeed: number,
	crouchSpeed: number,
	slideSpeed: number,
	slideDuration: number,
	slideCooldown: number,
	dashSpeed: number,
	dashDuration: number,
	dashCooldown: number,
	maxDashes: number,
	jumpPower: number,
	doubleJumpPower: number,
	maxJumps: number,
	wallRunSpeed: number,
	wallRunDuration: number,
	mantleHeight: number,
	coyoteTime: number,
	jumpBufferTime: number,
}

local DEFAULT_CONFIG: MovementConfig = {
	walkSpeed = 16,
	sprintSpeed = 24,
	crouchSpeed = 8,
	slideSpeed = 32,
	slideDuration = 0.8,
	slideCooldown = 1.5,
	dashSpeed = 50,
	dashDuration = 0.2,
	dashCooldown = 3,
	maxDashes = 2,
	jumpPower = 50,
	doubleJumpPower = 45,
	maxJumps = 2,
	wallRunSpeed = 20,
	wallRunDuration = 1.5,
	mantleHeight = 7,
	coyoteTime = 0.15,
	jumpBufferTime = 0.12,
}

function MovementSystem.new(config: MovementConfig?)
	local self = setmetatable({}, MovementSystem)
	self.config = config or DEFAULT_CONFIG
	self.state = {
		isSprinting = false,
		isCrouching = false,
		isSliding = false,
		isDashing = false,
		isWallRunning = false,
		jumpsRemaining = self.config.maxJumps,
		dashesRemaining = self.config.maxDashes,
		lastGroundedTime = 0,
		lastJumpRequest = 0,
		lastSlideTime = -math.huge,
		lastDashTime = -math.huge,
		slideTimer = 0,
		dashTimer = 0,
		wallRunTimer = 0,
		wallNormal = Vector3.zero,
		moveDirection = Vector3.zero,
	}
	self._connections = {}
	return self
end

function MovementSystem:bind(character: Model)
	self.character = character
	self.humanoid = character:WaitForChild("Humanoid")
	self.rootPart = character:WaitForChild("HumanoidRootPart")

	self.humanoid.WalkSpeed = self.config.walkSpeed

	table.insert(self._connections, RunService.Heartbeat:Connect(function(dt)
		self:update(dt)
	end))

	table.insert(self._connections, self.humanoid.StateChanged:Connect(function(_, new)
		if new == Enum.HumanoidStateType.Landed then
			self:onLanded()
		end
	end))
end

function MovementSystem:update(dt: number)
	local now = tick()

	if self.humanoid.FloorMaterial ~= Enum.Material.Air then
		self.state.lastGroundedTime = now
		if not self.state.isSliding then
			self.state.jumpsRemaining = self.config.maxJumps
		end
		self.state.dashesRemaining = self.config.maxDashes
	end

	if self.state.isSliding then
		self.state.slideTimer -= dt
		if self.state.slideTimer <= 0 then
			self:endSlide()
		end
	end

	if self.state.isDashing then
		self.state.dashTimer -= dt
		if self.state.dashTimer <= 0 then
			self:endDash()
		end
	end

	if self.state.isWallRunning then
		self.state.wallRunTimer -= dt
		if self.state.wallRunTimer <= 0 or self.humanoid.FloorMaterial ~= Enum.Material.Air then
			self:endWallRun()
		end
	end

	if now - self.state.lastJumpRequest < self.config.jumpBufferTime then
		if self:canJump() then
			self:executeJump()
			self.state.lastJumpRequest = 0
		end
	end

	self:updateSpeed()
	self:checkWallRun()
end

function MovementSystem:updateSpeed()
	if self.state.isDashing then return end

	if self.state.isSliding then
		local t = 1 - (self.state.slideTimer / self.config.slideDuration)
		local speed = self.config.slideSpeed * (1 - t * 0.6)
		self.humanoid.WalkSpeed = speed
	elseif self.state.isCrouching then
		self.humanoid.WalkSpeed = self.config.crouchSpeed
	elseif self.state.isSprinting then
		self.humanoid.WalkSpeed = self.config.sprintSpeed
	else
		self.humanoid.WalkSpeed = self.config.walkSpeed
	end
end

function MovementSystem:canJump(): boolean
	local now = tick()
	local grounded = self.humanoid.FloorMaterial ~= Enum.Material.Air
	local coyote = (now - self.state.lastGroundedTime) <= self.config.coyoteTime
	return self.state.jumpsRemaining > 0 and (grounded or coyote or self.state.jumpsRemaining < self.config.maxJumps)
end

function MovementSystem:requestJump()
	self.state.lastJumpRequest = tick()
	if self:canJump() then
		self:executeJump()
	end
end

function MovementSystem:executeJump()
	local isFirst = self.state.jumpsRemaining == self.config.maxJumps
	local power = isFirst and self.config.jumpPower or self.config.doubleJumpPower
	self.state.jumpsRemaining -= 1

	self.rootPart.AssemblyLinearVelocity = Vector3.new(
		self.rootPart.AssemblyLinearVelocity.X,
		power,
		self.rootPart.AssemblyLinearVelocity.Z
	)

	if self.state.isSliding then self:endSlide() end
	if self.state.isWallRunning then
		local wallKick = self.state.wallNormal * 30
		self.rootPart.AssemblyLinearVelocity += wallKick
		self:endWallRun()
	end
end

function MovementSystem:sprint(active: boolean)
	self.state.isSprinting = active
	if active and self.state.isCrouching then
		self.state.isCrouching = false
	end
end

function MovementSystem:crouch(active: boolean)
	self.state.isCrouching = active
	if active then
		self.state.isSprinting = false
		local camera = workspace.CurrentCamera
		if camera then
			-- scale character to crouch height (game-specific implementation)
		end
	end
end

function MovementSystem:slide()
	local now = tick()
	if self.state.isSliding then return end
	if (now - self.state.lastSlideTime) < self.config.slideCooldown then return end
	if self.humanoid.FloorMaterial == Enum.Material.Air then return end

	self.state.isSliding = true
	self.state.slideTimer = self.config.slideDuration
	self.state.lastSlideTime = now
	self.humanoid.WalkSpeed = self.config.slideSpeed
end

function MovementSystem:endSlide()
	self.state.isSliding = false
end

function MovementSystem:dash(direction: Vector3)
	local now = tick()
	if self.state.isDashing then return end
	if self.state.dashesRemaining <= 0 then return end
	if (now - self.state.lastDashTime) < self.config.dashCooldown then return end

	self.state.isDashing = true
	self.state.dashTimer = self.config.dashDuration
	self.state.lastDashTime = now
	self.state.dashesRemaining -= 1

	local dashDir = direction.Unit
	self.rootPart.AssemblyLinearVelocity = dashDir * self.config.dashSpeed + Vector3.new(0, 5, 0)
end

function MovementSystem:endDash()
	self.state.isDashing = false
	local vel = self.rootPart.AssemblyLinearVelocity
	self.rootPart.AssemblyLinearVelocity = Vector3.new(vel.X * 0.3, vel.Y, vel.Z * 0.3)
end

function MovementSystem:checkWallRun()
	if self.state.isWallRunning then return end
	if self.humanoid.FloorMaterial ~= Enum.Material.Air then return end
	if self.rootPart.AssemblyLinearVelocity.Y < -10 then return end

	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { self.character }

	for _, dir in { self.rootPart.CFrame.RightVector, -self.rootPart.CFrame.RightVector } do
		local result = workspace:Raycast(self.rootPart.Position, dir * 3, params)
		if result and result.Normal.Y < 0.1 then
			self:startWallRun(result.Normal)
			break
		end
	end
end

function MovementSystem:startWallRun(wallNormal: Vector3)
	self.state.isWallRunning = true
	self.state.wallRunTimer = self.config.wallRunDuration
	self.state.wallNormal = wallNormal

	local forward = self.rootPart.CFrame.LookVector
	local wallDir = forward - forward:Dot(wallNormal) * wallNormal
	self.rootPart.AssemblyLinearVelocity = wallDir.Unit * self.config.wallRunSpeed + Vector3.new(0, 10, 0)
end

function MovementSystem:endWallRun()
	self.state.isWallRunning = false
end

function MovementSystem:checkMantle(): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { self.character }

	local origin = self.rootPart.Position + Vector3.new(0, 2, 0)
	local forward = self.rootPart.CFrame.LookVector

	local wallCheck = workspace:Raycast(origin, forward * 3, params)
	if not wallCheck then return false end

	local topOrigin = origin + Vector3.new(0, self.config.mantleHeight, 0)
	local topCheck = workspace:Raycast(topOrigin, forward * 3, params)
	if topCheck then return false end

	local ledgeCheck = workspace:Raycast(topOrigin + forward * 2, Vector3.new(0, -self.config.mantleHeight, 0), params)
	if not ledgeCheck then return false end

	local targetPos = ledgeCheck.Position + Vector3.new(0, 3, 0) + forward * 2
	self.rootPart.CFrame = CFrame.new(targetPos, targetPos + forward)
	self.rootPart.AssemblyLinearVelocity = Vector3.zero

	return true
end

function MovementSystem:onLanded()
	self.state.jumpsRemaining = self.config.maxJumps
	if self.state.isWallRunning then
		self:endWallRun()
	end
end

function MovementSystem:destroy()
	for _, conn in self._connections do
		conn:Disconnect()
	end
end

return MovementSystem
