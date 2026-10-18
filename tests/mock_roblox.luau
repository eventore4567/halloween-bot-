--!nocheck
-- Environnement Roblox simulé pour tester BloxHub hors du jeu.
-- Objectif : exécuter le vrai code du hub et faire échouer les tests sur les erreurs
-- que Roblox lèverait (propriété inconnue, mauvais type, Enum inexistant, Parent verrouillé…).
-- Ce n'est PAS Roblox : le rendu, la physique et le réseau réels ne sont pas simulés.

local M = {}

---------------------------------------------------------------------------
-- Ordonnanceur virtuel (task.*)
---------------------------------------------------------------------------
local clock = 0
local queue = {} -- { thread, at, args }
local cancelled = setmetatable({}, { __mode = "k" })

local function schedule(thread, at, ...)
	table.insert(queue, { thread = thread, at = at, args = table.pack(...) })
end

local errors = {}
M.errors = errors

local function resume(thread, ...)
	if cancelled[thread] or coroutine.status(thread) == "dead" then
		return
	end
	local ok, err = coroutine.resume(thread, ...)
	if not ok then
		table.insert(errors, debug.traceback(thread, tostring(err)))
	end
end

local task = {}
function task.spawn(fn, ...)
	local thread = type(fn) == "thread" and fn or coroutine.create(fn)
	resume(thread, ...)
	return thread
end
function task.defer(fn, ...)
	local thread = type(fn) == "thread" and fn or coroutine.create(fn)
	schedule(thread, clock, ...)
	return thread
end
function task.delay(t, fn, ...)
	local thread = type(fn) == "thread" and fn or coroutine.create(fn)
	schedule(thread, clock + (t or 0), ...)
	return thread
end
function task.wait(t)
	t = math.max(t or 0, 1 / 60)
	local thread = coroutine.running()
	local start = clock
	assert(coroutine.isyieldable(), "task.wait appelé hors d'un thread")
	schedule(thread, clock + t)
	coroutine.yield()
	return clock - start
end
function task.cancel(thread)
	cancelled[thread] = true
	for i = #queue, 1, -1 do
		if queue[i].thread == thread then
			table.remove(queue, i)
		end
	end
	if coroutine.status(thread) == "suspended" then
		coroutine.close(thread)
	end
end
M.task = task

function M.now()
	return clock
end

-- Avance le temps virtuel par pas de 1/60 s.
function M.advance(seconds)
	local target = clock + seconds
	repeat
		clock = math.min(target, clock + 1 / 60)
		local due = {}
		for i = #queue, 1, -1 do
			if queue[i].at <= clock then
				table.insert(due, 1, table.remove(queue, i))
			end
		end
		table.sort(due, function(a, b)
			return a.at < b.at
		end)
		for _, item in ipairs(due) do
			resume(item.thread, table.unpack(item.args, 1, item.args.n))
		end
	until clock >= target
end

function M.pending()
	return #queue
end

---------------------------------------------------------------------------
-- Types de données
---------------------------------------------------------------------------
local function typed(name, t, mt)
	mt = mt or {}
	mt.__type = name
	mt.__index = mt.__index or mt
	return setmetatable(t, mt)
end

local UDimMT = { __type = "UDim" }
UDimMT.__index = UDimMT
local UDim = {
	new = function(s, o)
		return setmetatable({ Scale = s or 0, Offset = o or 0 }, UDimMT)
	end,
}

local UDim2MT = { __type = "UDim2" }
UDim2MT.__index = UDim2MT
UDim2MT.__eq = function(a, b)
	return a.X.Scale == b.X.Scale and a.X.Offset == b.X.Offset and a.Y.Scale == b.Y.Scale and a.Y.Offset == b.Y.Offset
end
local UDim2 = {}
function UDim2.new(xs, xo, ys, yo)
	return setmetatable({ X = UDim.new(xs, xo), Y = UDim.new(ys, yo) }, UDim2MT)
end
function UDim2.fromOffset(x, y)
	return UDim2.new(0, x or 0, 0, y or 0)
end
function UDim2.fromScale(x, y)
	return UDim2.new(x or 0, 0, y or 0, 0)
end

local Vector2MT = { __type = "Vector2" }
Vector2MT.__index = Vector2MT
local Vector2 = {}
function Vector2.new(x, y)
	return setmetatable({ X = x or 0, Y = y or 0 }, Vector2MT)
end
Vector2MT.__sub = function(a, b)
	return Vector2.new(a.X - b.X, a.Y - b.Y)
end
Vector2MT.__add = function(a, b)
	return Vector2.new(a.X + b.X, a.Y + b.Y)
end
Vector2MT.__eq = function(a, b)
	return a.X == b.X and a.Y == b.Y
end

local Color3MT = { __type = "Color3" }
Color3MT.__index = Color3MT
Color3MT.__eq = function(a, b)
	return a.R == b.R and a.G == b.G and a.B == b.B
end
local Color3 = {}
function Color3.new(r, g, b)
	return setmetatable({ R = r or 0, G = g or 0, B = b or 0 }, Color3MT)
end
function Color3.fromRGB(r, g, b)
	assert(type(r) == "number" and type(g) == "number" and type(b) == "number", "Color3.fromRGB attend 3 nombres")
	return Color3.new(r / 255, g / 255, b / 255)
end

local TweenInfo = {
	new = function(time, style, dir)
		return typed("TweenInfo", { Time = time, EasingStyle = style, EasingDirection = dir })
	end,
}

---------------------------------------------------------------------------
-- Enum (liste fermée : un nom inconnu lève une erreur comme dans Roblox)
---------------------------------------------------------------------------
local ENUMS = {
	Font = { "Gotham", "GothamMedium", "GothamBold", "Code", "SourceSans" },
	TextXAlignment = { "Left", "Right", "Center" },
	TextYAlignment = { "Top", "Center", "Bottom" },
	AutomaticSize = { "None", "X", "Y", "XY" },
	SortOrder = { "LayoutOrder", "Name" },
	FillDirection = { "Horizontal", "Vertical" },
	VerticalAlignment = { "Top", "Center", "Bottom" },
	HorizontalAlignment = { "Left", "Center", "Right" },
	ApplyStrokeMode = { "Contextual", "Border" },
	ZIndexBehavior = { "Global", "Sibling" },
	ScrollingDirection = { "X", "Y", "XY" },
	TextTruncate = { "None", "AtEnd" },
	EasingStyle = { "Linear", "Quad", "Quint", "Sine" },
	EasingDirection = { "In", "Out", "InOut" },
	UserInputType = { "MouseButton1", "MouseButton2", "MouseMovement", "Touch", "Keyboard" },
	UserInputState = { "Begin", "Change", "End" },
	KeyCode = { "RightShift", "RightControl", "LeftShift", "F6", "Insert", "A", "E", "Unknown" },
}

local EnumItemMT = { __type = "EnumItem" }
EnumItemMT.__index = EnumItemMT
EnumItemMT.__tostring = function(self)
	return "Enum." .. self.EnumType .. "." .. self.Name
end

local Enum = {}
for enumName, items in pairs(ENUMS) do
	local e = {}
	for i, itemName in ipairs(items) do
		e[itemName] = setmetatable({ Name = itemName, Value = i - 1, EnumType = enumName }, EnumItemMT)
	end
	Enum[enumName] = setmetatable(e, {
		__index = function(_, k)
			error(tostring(k) .. " is not a valid member of \"Enum." .. enumName .. "\"", 2)
		end,
	})
end
setmetatable(Enum, {
	__index = function(_, k)
		error(tostring(k) .. " is not a valid enum type", 2)
	end,
})

local function typeof(v)
	local mt = getmetatable(v)
	if type(mt) == "table" and mt.__type then
		return mt.__type
	end
	return type(v)
end

---------------------------------------------------------------------------
-- Signaux
---------------------------------------------------------------------------
local SignalMT = { __type = "RBXScriptSignal" }
SignalMT.__index = SignalMT
local liveConnections = 0
M.liveConnections = function()
	return liveConnections
end

local function newSignal()
	return setmetatable({ handlers = {} }, SignalMT)
end
function SignalMT:Connect(fn)
	assert(type(fn) == "function", "Connect attend une fonction")
	local conn = { Connected = true }
	liveConnections += 1
	local signal = self
	function conn.Disconnect()
		if conn.Connected then
			conn.Connected = false
			liveConnections -= 1
			for i, h in ipairs(signal.handlers) do
				if h == conn then
					table.remove(signal.handlers, i)
					break
				end
			end
		end
	end
	conn.fn = fn
	table.insert(self.handlers, conn)
	return setmetatable(conn, { __type = "RBXScriptConnection", __index = { Disconnect = conn.Disconnect } })
end
function SignalMT:Fire(...)
	local list = table.clone(self.handlers)
	for _, conn in ipairs(list) do
		if conn.Connected then
			task.spawn(conn.fn, ...)
		end
	end
end
function SignalMT:Wait()
	local thread = coroutine.running()
	local conn
	conn = self:Connect(function(...)
		conn:Disconnect()
		task.spawn(thread, ...)
	end)
	return coroutine.yield()
end
function SignalMT:DisconnectAll()
	for _, conn in ipairs(table.clone(self.handlers)) do
		conn.Disconnect()
	end
end

---------------------------------------------------------------------------
-- Instances
---------------------------------------------------------------------------
local T_UDIM2, T_UDIM, T_V2, T_C3, T_NUM, T_BOOL, T_STR = "UDim2", "UDim", "Vector2", "Color3", "number", "boolean", "string"
local function E(name)
	return "Enum:" .. name
end

local GUIBASE = {
	Name = T_STR, Position = T_UDIM2, Size = T_UDIM2, AnchorPoint = T_V2, BackgroundColor3 = T_C3,
	BackgroundTransparency = T_NUM, BorderSizePixel = T_NUM, Visible = T_BOOL, ZIndex = T_NUM,
	LayoutOrder = T_NUM, ClipsDescendants = T_BOOL, AutomaticSize = E("AutomaticSize"), Active = T_BOOL,
	Rotation = T_NUM, AbsolutePosition = T_V2, AbsoluteSize = T_V2,
}
local TEXT = {
	Text = T_STR, Font = E("Font"), TextSize = T_NUM, TextColor3 = T_C3, TextXAlignment = E("TextXAlignment"),
	TextYAlignment = E("TextYAlignment"), TextWrapped = T_BOOL, TextTruncate = E("TextTruncate"), RichText = T_BOOL,
	TextTransparency = T_NUM, TextScaled = T_BOOL,
}
local function merge(...)
	local out = {}
	for _, t in ipairs({ ... }) do
		for k, v in pairs(t) do
			out[k] = v
		end
	end
	return out
end

local CLASSES = {
	Frame = { props = GUIBASE, gui = true },
	TextLabel = { props = merge(GUIBASE, TEXT), gui = true },
	TextButton = { props = merge(GUIBASE, TEXT, { AutoButtonColor = T_BOOL }), gui = true, button = true },
	TextBox = { props = merge(GUIBASE, TEXT, { PlaceholderText = T_STR, PlaceholderColor3 = T_C3, ClearTextOnFocus = T_BOOL }), gui = true },
	ScrollingFrame = {
		props = merge(GUIBASE, {
			CanvasSize = T_UDIM2, AutomaticCanvasSize = E("AutomaticSize"), ScrollBarThickness = T_NUM,
			ScrollBarImageColor3 = T_C3, ScrollingDirection = E("ScrollingDirection"), CanvasPosition = T_V2,
		}),
		gui = true,
	},
	ScreenGui = { props = { Name = T_STR, ResetOnSpawn = T_BOOL, IgnoreGuiInset = T_BOOL, ZIndexBehavior = E("ZIndexBehavior"), DisplayOrder = T_NUM, Enabled = T_BOOL } },
	UICorner = { props = { Name = T_STR, CornerRadius = T_UDIM } },
	UIStroke = { props = { Name = T_STR, Color = T_C3, Thickness = T_NUM, ApplyStrokeMode = E("ApplyStrokeMode"), Transparency = T_NUM } },
	UIPadding = { props = { Name = T_STR, PaddingTop = T_UDIM, PaddingRight = T_UDIM, PaddingBottom = T_UDIM, PaddingLeft = T_UDIM } },
	UIListLayout = { props = { Name = T_STR, Padding = T_UDIM, SortOrder = E("SortOrder"), FillDirection = E("FillDirection"), VerticalAlignment = E("VerticalAlignment"), HorizontalAlignment = E("HorizontalAlignment") } },
	UIGridLayout = { props = { Name = T_STR, CellPadding = T_UDIM2, CellSize = T_UDIM2, SortOrder = E("SortOrder") } },
	UIScale = { props = { Name = T_STR, Scale = T_NUM } },
	Folder = { props = { Name = T_STR } },
	Model = { props = { Name = T_STR } },
	Backpack = { props = { Name = T_STR } },
	PlayerGui = { props = { Name = T_STR } },
	Tool = { props = { Name = T_STR, ToolTip = T_STR } },
	IntValue = { props = { Name = T_STR, Value = T_NUM } },
	NumberValue = { props = { Name = T_STR, Value = T_NUM } },
	StringValue = { props = { Name = T_STR, Value = T_STR } },
	BoolValue = { props = { Name = T_STR, Value = T_BOOL } },
	RemoteFunction = { props = { Name = T_STR } },
	Player = { props = { Name = T_STR, UserId = T_NUM } },
	Service = { props = { Name = T_STR } },
}

local ISA = {
	GuiObject = { Frame = true, TextLabel = true, TextButton = true, TextBox = true, ScrollingFrame = true },
	GuiButton = { TextButton = true },
	ValueBase = { IntValue = true, NumberValue = true, StringValue = true, BoolValue = true },
	LayerCollector = { ScreenGui = true },
	Instance = {},
}

local DEFAULTS = {
	[T_UDIM2] = function()
		return UDim2.new()
	end,
	[T_UDIM] = function()
		return UDim.new()
	end,
	[T_V2] = function()
		return Vector2.new()
	end,
	[T_C3] = function()
		return Color3.new(1, 1, 1)
	end,
	[T_NUM] = function()
		return 0
	end,
	[T_BOOL] = function()
		return false
	end,
	[T_STR] = function()
		return ""
	end,
}
local TRUE_DEFAULTS = { Visible = true, Enabled = true, ResetOnSpawn = true, ClearTextOnFocus = true, AutoButtonColor = true, Scale = 1, Thickness = 1, TextSize = 14 }

local EVENTS = {
	AncestryChanged = true, Changed = true, ChildAdded = true, ChildRemoved = true, Destroying = true,
	MouseButton1Click = "button", MouseEnter = "gui", MouseLeave = "gui", InputBegan = "gui", InputEnded = "gui", InputChanged = "gui",
}

local InstanceMT = { __type = "Instance" }
local allInstances = setmetatable({}, { __mode = "k" })
M.liveInstances = function()
	local n = 0
	for inst in pairs(allInstances) do
		if not rawget(inst, "_destroyed") then
			n += 1
		end
	end
	return n
end

local function checkType(class, prop, value)
	local expected = CLASSES[class] and CLASSES[class].props[prop]
	if not expected then
		return false
	end
	if expected:sub(1, 5) == "Enum:" then
		local enumName = expected:sub(6)
		if typeof(value) ~= "EnumItem" or value.EnumType ~= enumName then
			error(("Unable to assign property %s. EnumItem of type %s expected, got %s"):format(prop, enumName, tostring(value)), 3)
		end
		return true
	end
	if typeof(value) ~= expected then
		error(("Unable to assign property %s. %s expected, got %s"):format(prop, expected, typeof(value)), 3)
	end
	return true
end

local methods = {}

local function newInstance(class, extra)
	assert(CLASSES[class], "Instance.new : classe non simulée « " .. tostring(class) .. " »")
	local inst = {
		ClassName = class,
		_props = { Name = class },
		_children = {},
		_events = {},
		_propSignals = {},
		_parent = nil,
		_destroyed = false,
		_parentLocked = false,
	}
	for k, v in pairs(extra or {}) do
		inst[k] = v
	end
	allInstances[inst] = true
	return setmetatable(inst, InstanceMT)
end
M.newInstance = newInstance

InstanceMT.__index = function(self, key)
	if methods[key] then
		return methods[key]
	end
	local props = rawget(self, "_props")
	if key == "Parent" then
		return rawget(self, "_parent")
	end
	if props[key] ~= nil then
		return props[key]
	end
	local custom = rawget(self, "_custom")
	if custom and custom[key] ~= nil then
		return custom[key]
	end
	local class = CLASSES[rawget(self, "ClassName")]
	local t = class.props[key]
	if t then
		if TRUE_DEFAULTS[key] ~= nil then
			return TRUE_DEFAULTS[key]
		end
		local d = DEFAULTS[t]
		if d then
			return d()
		end
		local enumName = t:sub(6)
		local first
		for _, item in pairs(Enum[enumName]) do
			if item.Value == 0 then
				first = item
			end
		end
		return first
	end
	local ev = EVENTS[key]
	if ev and (ev == true or (ev == "gui" and class.gui) or (ev == "button" and class.button)) then
		local events = rawget(self, "_events")
		events[key] = events[key] or newSignal()
		return events[key]
	end
	for _, child in ipairs(rawget(self, "_children")) do
		if child.Name == key then
			return child
		end
	end
	error(tostring(key) .. " is not a valid member of " .. rawget(self, "ClassName") .. " \"" .. tostring(props.Name) .. "\"", 2)
end

local function fireProp(self, key)
	local s = rawget(self, "_propSignals")[key]
	if s then
		s:Fire()
	end
	local changed = rawget(self, "_events").Changed
	if changed then
		changed:Fire(key)
	end
end

local function setParent(self, parent)
	if rawget(self, "_parentLocked") then
		error("The Parent property of " .. tostring(self.Name) .. " is locked, current parent: NULL", 3)
	end
	if parent ~= nil and typeof(parent) ~= "Instance" then
		error("Parent doit être une Instance", 3)
	end
	local old = rawget(self, "_parent")
	if old == parent then
		return
	end
	if old then
		local list = rawget(old, "_children")
		for i, c in ipairs(list) do
			if c == self then
				table.remove(list, i)
				break
			end
		end
	end
	rawset(self, "_parent", parent)
	if parent then
		table.insert(rawget(parent, "_children"), self)
		if rawget(parent, "_onChildAdded") then
			rawget(parent, "_onChildAdded")(parent, self)
		end
	end
	local ev = rawget(self, "_events").AncestryChanged
	if ev then
		ev:Fire(self, parent)
	end
end

InstanceMT.__newindex = function(self, key, value)
	if key == "Parent" then
		setParent(self, value)
		return
	end
	local class = rawget(self, "ClassName")
	local custom = rawget(self, "_custom")
	if custom and custom[key] ~= nil then
		custom[key] = value
		return
	end
	if not checkType(class, key, value) then
		error(tostring(key) .. " is not a valid member of " .. class, 2)
	end
	local props = rawget(self, "_props")
	if props[key] ~= value then
		props[key] = value
		fireProp(self, key)
	end
end

function methods:GetChildren()
	return table.clone(rawget(self, "_children"))
end
function methods:GetDescendants()
	local out = {}
	local function walk(inst)
		for _, c in ipairs(rawget(inst, "_children")) do
			table.insert(out, c)
			walk(c)
		end
	end
	walk(self)
	return out
end
function methods:FindFirstChild(name, recursive)
	for _, c in ipairs(rawget(self, "_children")) do
		if c.Name == name then
			return c
		end
	end
	if recursive then
		for _, c in ipairs(rawget(self, "_children")) do
			local f = c:FindFirstChild(name, true)
			if f then
				return f
			end
		end
	end
	return nil
end
function methods:IsA(className)
	local cn = rawget(self, "ClassName")
	if cn == className or className == "Instance" then
		return true
	end
	local set = ISA[className]
	return set ~= nil and set[cn] == true
end
function methods:FindFirstChildOfClass(className)
	for _, c in ipairs(rawget(self, "_children")) do
		if rawget(c, "ClassName") == className then
			return c
		end
	end
	return nil
end
function methods:FindFirstChildWhichIsA(className)
	for _, c in ipairs(rawget(self, "_children")) do
		if c:IsA(className) then
			return c
		end
	end
	return nil
end
function methods:WaitForChild(name, timeout)
	local found = self:FindFirstChild(name)
	local waited = 0
	while not found and waited < (timeout or 5) do
		waited += task.wait(0.1)
		found = self:FindFirstChild(name)
	end
	return found
end
function methods:GetPropertyChangedSignal(prop)
	local class = CLASSES[rawget(self, "ClassName")]
	assert(class.props[prop], prop .. " is not a valid property name.")
	local signals = rawget(self, "_propSignals")
	signals[prop] = signals[prop] or newSignal()
	return signals[prop]
end
function methods:Destroy()
	if rawget(self, "_destroyed") then
		return
	end
	for _, c in ipairs(table.clone(rawget(self, "_children"))) do
		c:Destroy()
	end
	if rawget(self, "_parent") then
		setParent(self, nil)
	end
	rawset(self, "_destroyed", true)
	rawset(self, "_parentLocked", true)
	for _, s in pairs(rawget(self, "_events")) do
		s:DisconnectAll()
	end
	for _, s in pairs(rawget(self, "_propSignals")) do
		s:DisconnectAll()
	end
end
function methods:GetFullName()
	local parts = {}
	local cur = self
	while cur do
		table.insert(parts, 1, cur.Name)
		cur = rawget(cur, "_parent")
	end
	return table.concat(parts, ".")
end
function methods:IsDescendantOf(other)
	local cur = rawget(self, "_parent")
	while cur do
		if cur == other then
			return true
		end
		cur = rawget(cur, "_parent")
	end
	return false
end

-- Méthodes spécifiques injectées via _custom.
local function withCustom(inst, custom)
	rawset(inst, "_custom", custom)
	return inst
end

local Instance = {
	new = function(class, parent)
		local inst = newInstance(class)
		if parent then
			inst.Parent = parent
		end
		return inst
	end,
}

---------------------------------------------------------------------------
-- JSON minimal (HttpService)
---------------------------------------------------------------------------
local function jsonEncode(v)
	local t = type(v)
	if t == "nil" then
		return "null"
	elseif t == "boolean" or t == "number" then
		return tostring(v)
	elseif t == "string" then
		return '"' .. v:gsub('[%c"\\]', function(ch)
			return ("\\u%04x"):format(string.byte(ch))
		end) .. '"'
	elseif t == "table" then
		if #v > 0 or next(v) == nil then
			local parts = {}
			for _, x in ipairs(v) do
				table.insert(parts, jsonEncode(x))
			end
			return "[" .. table.concat(parts, ",") .. "]"
		end
		local parts = {}
		for k, x in pairs(v) do
			table.insert(parts, jsonEncode(tostring(k)) .. ":" .. jsonEncode(x))
		end
		return "{" .. table.concat(parts, ",") .. "}"
	end
	error("JSONEncode : type non supporté " .. t)
end

local function jsonDecode(s)
	local i = 1
	local function ws()
		i = s:find("[^ \t\r\n]", i) or (#s + 1)
	end
	local value
	local function str()
		local out = {}
		i += 1
		while true do
			local ch = s:sub(i, i)
			if ch == "" then
				error("JSON : chaîne non terminée")
			elseif ch == '"' then
				i += 1
				break
			elseif ch == "\\" then
				local n = s:sub(i + 1, i + 1)
				if n == "u" then
					table.insert(out, utf8.char(tonumber(s:sub(i + 2, i + 5), 16)))
					i += 6
				else
					local map = { n = "\n", t = "\t", r = "\r", b = "\b", f = "\f" }
					table.insert(out, map[n] or n)
					i += 2
				end
			else
				table.insert(out, ch)
				i += 1
			end
		end
		return table.concat(out)
	end
	function value()
		ws()
		local ch = s:sub(i, i)
		if ch == "{" then
			local obj = {}
			i += 1
			ws()
			if s:sub(i, i) == "}" then
				i += 1
				return obj
			end
			while true do
				ws()
				local k = str()
				ws()
				assert(s:sub(i, i) == ":", "JSON : ':' attendu")
				i += 1
				obj[k] = value()
				ws()
				local sep = s:sub(i, i)
				i += 1
				if sep == "}" then
					return obj
				end
				assert(sep == ",", "JSON : ',' attendu")
			end
		elseif ch == "[" then
			local arr = {}
			i += 1
			ws()
			if s:sub(i, i) == "]" then
				i += 1
				return arr
			end
			while true do
				table.insert(arr, value())
				ws()
				local sep = s:sub(i, i)
				i += 1
				if sep == "]" then
					return arr
				end
				assert(sep == ",", "JSON : ',' attendu")
			end
		elseif ch == '"' then
			return str()
		elseif s:sub(i, i + 3) == "true" then
			i += 4
			return true
		elseif s:sub(i, i + 4) == "false" then
			i += 5
			return false
		elseif s:sub(i, i + 3) == "null" then
			i += 4
			return nil
		else
			local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
			assert(num and #num > 0, "JSON invalide à la position " .. i)
			i += #num
			return tonumber(num)
		end
	end
	local result = value()
	return result
end
M.jsonDecode = jsonDecode

---------------------------------------------------------------------------
-- Construction d'un monde (game, services, joueur, exécuteur)
---------------------------------------------------------------------------
-- opts : {
--   placeId, sources = { [url] = body }, files = bool, gethui = bool, coreguiBlocked = bool,
--   player = { level, beli, fragments, race, fruit, tools = { {name, mastery, tip, equipped} } },
--   inventory = table | "hang" | nil,
-- }
function M.world(opts)
	opts = opts or {}
	local env = {}
	local log = { warns = {}, setcore = {}, http = {} }

	local function service(name, custom)
		local s = newInstance("Service")
		s.Name = name
		if custom then
			withCustom(s, custom)
		end
		return s
	end

	-- Joueur local
	local player = newInstance("Player")
	player.Name = "TestPlayer"
	local playerGui = newInstance("PlayerGui")
	playerGui.Name = "PlayerGui"
	playerGui.Parent = player
	local backpack = newInstance("Backpack")
	backpack.Name = "Backpack"
	backpack.Parent = player
	local character = newInstance("Model")
	character.Name = "TestPlayer"
	withCustom(player, { Character = character })

	local p = opts.player
	if p then
		local data = newInstance("Folder")
		data.Name = "Data"
		local function val(class, name, v)
			local x = newInstance(class)
			x.Name = name
			x.Value = v
			x.Parent = data
			return x
		end
		val("IntValue", "Level", p.level or 1)
		val("IntValue", "Beli", p.beli or 0)
		val("IntValue", "Fragments", p.fragments or 0)
		local race = val("StringValue", "Race", p.race or "Human")
		if p.evolved then
			local ev = newInstance("BoolValue")
			ev.Name = "Evolved"
			ev.Value = true
			ev.Parent = race
		end
		val("StringValue", "DevilFruit", p.fruit or "")
		data.Parent = player
		for _, t in ipairs(p.tools or {}) do
			local tool = newInstance("Tool")
			tool.Name = t.name
			tool.ToolTip = t.tip or ""
			if t.mastery then
				local lv = newInstance("IntValue")
				lv.Name = "Level"
				lv.Value = t.mastery
				lv.Parent = tool
			end
			tool.Parent = t.equipped and character or backpack
		end
	end

	local players = service("Players", { LocalPlayer = player })
	local coreGui = service("CoreGui")
	local hidden = newInstance("Folder")
	hidden.Name = "HiddenUI"

	local uis = service("UserInputService", {
		GetFocusedTextBox = function()
			return nil
		end,
	})
	rawget(uis, "_events").InputBegan = newSignal()
	rawget(uis, "_events").InputChanged = newSignal()
	rawget(uis, "_events").InputEnded = newSignal()
	-- Les services ne sont pas des GuiObject : on expose les signaux d'entrée explicitement.
	withCustom(uis, {
		GetFocusedTextBox = function()
			return nil
		end,
		InputBegan = rawget(uis, "_events").InputBegan,
		InputChanged = rawget(uis, "_events").InputChanged,
		InputEnded = rawget(uis, "_events").InputEnded,
	})

	local tweens = { count = 0 }
	local tweenService = service("TweenService", {
		Create = function(_, inst, info, props)
			assert(typeof(inst) == "Instance", "TweenService:Create : instance attendue")
			assert(typeof(info) == "TweenInfo", "TweenService:Create : TweenInfo attendu")
			for k, v in pairs(props) do
				local class = CLASSES[rawget(inst, "ClassName")]
				assert(class.props[k], "Tween : propriété inconnue " .. k)
				assert(typeof(v) == typeof(inst[k]), "Tween : type incompatible pour " .. k)
			end
			return {
				Play = function()
					tweens.count += 1
					for k, v in pairs(props) do
						inst[k] = v
					end
				end,
			}
		end,
	})

	local httpService = service("HttpService", {
		JSONEncode = function(_, v)
			return jsonEncode(v)
		end,
		JSONDecode = function(_, s)
			return jsonDecode(s)
		end,
	})

	local replicated = service("ReplicatedStorage")
	if opts.inventory ~= nil then
		local remotes = newInstance("Folder")
		remotes.Name = "Remotes"
		remotes.Parent = replicated
		local comm = newInstance("RemoteFunction")
		comm.Name = "CommF_"
		local invokes = 0
		withCustom(comm, {
			InvokeServer = function(_, action)
				invokes += 1
				log.invokes = invokes
				assert(action == "getInventory", "seule la lecture d'inventaire est autorisée, reçu : " .. tostring(action))
				if opts.inventory == "hang" then
					task.wait(1000)
				end
				task.wait(0.5)
				return opts.inventory
			end,
		})
		comm.Parent = remotes
	end

	local starterGui = service("StarterGui", {
		SetCore = function(_, name, data)
			table.insert(log.setcore, { name = name, data = data })
		end,
	})

	local services = {
		Players = players, CoreGui = coreGui, UserInputService = uis, TweenService = tweenService,
		HttpService = httpService, ReplicatedStorage = replicated, StarterGui = starterGui,
		RunService = service("RunService"),
	}

	local game = newInstance("Service")
	game.Name = "Game"
	withCustom(game, {
		PlaceId = opts.placeId or 2753915549,
		GetService = function(_, name)
			if name == "CoreGui" and opts.coreguiBlocked then
				return setmetatable({}, {
					__index = function()
						error("The current thread cannot access 'CoreGui' (lacking capability)")
					end,
					__newindex = function()
						error("The current thread cannot access 'CoreGui' (lacking capability)")
					end,
					__type = "Instance",
				})
			end
			return services[name] or error("service non simulé : " .. tostring(name))
		end,
		IsLoaded = function()
			return true
		end,
		HttpGet = function(_, url)
			table.insert(log.http, url)
			task.wait(0.05)
			local body = opts.sources and opts.sources[url]
			if body == nil then
				return "404: Not Found"
			end
			return body
		end,
	})

	-- Si CoreGui est bloqué, parent vers CoreGui doit échouer.
	if opts.coreguiBlocked then
		rawset(coreGui, "_onChildAdded", function()
			error("The current thread cannot access 'CoreGui' (lacking capability)")
		end)
	end

	local workspace = newInstance("Service")
	withCustom(workspace, { CurrentCamera = { ViewportSize = Vector2.new(1440, 900) } })

	-- Système de fichiers en mémoire
	local fs = {}
	local folders = {}
	local genv = {}

	env.game = game
	env.workspace = workspace
	env.Instance = Instance
	env.Enum = Enum
	env.UDim = UDim
	env.UDim2 = UDim2
	env.Vector2 = Vector2
	env.Color3 = Color3
	env.TweenInfo = TweenInfo
	env.typeof = typeof
	env.task = task
	env.tick = function()
		return clock
	end
	env.warn = function(...)
		local parts = {}
		for _, v in ipairs({ ... }) do
			table.insert(parts, tostring(v))
		end
		table.insert(log.warns, table.concat(parts, " "))
	end
	env.getgenv = function()
		return genv
	end
	env.identifyexecutor = function()
		return "MockExec", "1.0"
	end
	if opts.gethui ~= false then
		env.gethui = function()
			return hidden
		end
	end
	if opts.files ~= false then
		env.writefile = function(path, content)
			assert(type(content) == "string")
			fs[path] = content
		end
		env.readfile = function(path)
			return fs[path] or error("fichier introuvable : " .. path)
		end
		env.isfile = function(path)
			return fs[path] ~= nil
		end
		env.isfolder = function(path)
			return folders[path] == true
		end
		env.makefolder = function(path)
			folders[path] = true
		end
		env.delfile = function(path)
			fs[path] = nil
		end
	end
	env.setclipboard = function(text)
		log.clipboard = text
	end

	-- Environnement global de l'exécuteur : fonctions natives Luau + API simulées.
	local G = setmetatable(env, { __index = _G })
	G._G = G

	return {
		env = G,
		genv = genv,
		game = game,
		player = player,
		playerGui = playerGui,
		backpack = backpack,
		character = character,
		coreGui = coreGui,
		hidden = hidden,
		uis = uis,
		fs = fs,
		log = log,
		tweens = tweens,
		services = services,
	}
end

-- Exécute un code source dans l'environnement d'un monde, dans un thread (comme un exécuteur).
function M.exec(world, source, chunkname)
	local fn, err = loadstring(source, chunkname or "=exec")
	assert(fn, err)
	setfenv(fn, world.env)
	-- Les chunks chargés via loadstring à l'intérieur doivent aussi voir l'environnement simulé.
	world.env.loadstring = function(src, name)
		local f, e = loadstring(src, name)
		if f then
			setfenv(f, world.env)
		end
		return f, e
	end
	local result
	local thread = coroutine.create(function()
		result = fn()
	end)
	resume(thread)
	return thread, function()
		return result
	end
end

M.Enum = Enum
M.Vector2 = Vector2
M.UDim2 = UDim2
M.typeof = typeof

-- Crée un objet InputObject simulé.
function M.input(kind, position, keyCode, state)
	return setmetatable({
		UserInputType = Enum.UserInputType[kind],
		Position = position or Vector2.new(),
		KeyCode = keyCode and Enum.KeyCode[keyCode] or Enum.KeyCode.Unknown,
		UserInputState = Enum.UserInputState[state or "Begin"],
	}, { __type = "InputObject" })
end

return M
