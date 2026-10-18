-- BloxHub / ui : fenêtre, navigation latérale, recherche et composants.
-- La fenêtre se déplace (barre de titre), se réduit (–), se masque (×) et se rouvre
-- avec le bouton flottant ◆ ou la touche configurée (RightShift par défaut).

return function(Hub)
	local Players = game:GetService("Players")
	local TweenService = game:GetService("TweenService")
	local UserInputService = game:GetService("UserInputService")

	local Compat = Hub.Modules.compat
	local Diag = Hub.Modules.diagnostics
	local Tasks = Hub.Modules.tasks
	local Config = Hub.Modules.config

	local GUI_NAME = "BloxHub_UI"
	local WIN_W, WIN_H = 660, 440
	local TITLE_H = 44
	local SIDEBAR_W = 172

	local Theme = {
		bg = Color3.fromRGB(13, 13, 18),
		panel = Color3.fromRGB(19, 19, 26),
		card = Color3.fromRGB(25, 25, 34),
		cardHover = Color3.fromRGB(33, 33, 45),
		input = Color3.fromRGB(16, 16, 22),
		stroke = Color3.fromRGB(40, 40, 54),
		accent = Color3.fromRGB(139, 92, 246),
		accentSoft = Color3.fromRGB(58, 42, 102),
		text = Color3.fromRGB(236, 236, 245),
		muted = Color3.fromRGB(148, 148, 168),
		ok = Color3.fromRGB(74, 222, 128),
		bad = Color3.fromRGB(248, 113, 113),
		warn = Color3.fromRGB(251, 191, 36),
		unknown = Color3.fromRGB(125, 125, 145),
		font = Enum.Font.Gotham,
		fontMedium = Enum.Font.GothamMedium,
		fontBold = Enum.Font.GothamBold,
	}

	local UI = {
		Theme = Theme,
		pages = {},
		pageList = {},
		searchIndex = {},
		current = nil,
		visible = true,
		minimized = false,
	}

	local now = type(tick) == "function" and tick or os.clock

	local order = 0
	local function nextOrder()
		order += 1
		return order
	end

	local function new(class, props, children)
		local inst = Instance.new(class)
		local parent
		for k, v in pairs(props or {}) do
			if k == "Parent" then
				parent = v
			else
				inst[k] = v
			end
		end
		for _, child in ipairs(children or {}) do
			child.Parent = inst
		end
		if parent then
			inst.Parent = parent
		end
		return inst
	end
	UI.new = new

	local function corner(r)
		return new("UICorner", { CornerRadius = UDim.new(0, r or 8) })
	end

	local function stroke(color, thickness)
		return new("UIStroke", {
			Color = color or Theme.stroke,
			Thickness = thickness or 1,
			ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
		})
	end

	local function padding(t, r, b, l)
		return new("UIPadding", {
			PaddingTop = UDim.new(0, t),
			PaddingRight = UDim.new(0, r or t),
			PaddingBottom = UDim.new(0, b or t),
			PaddingLeft = UDim.new(0, l or r or t),
		})
	end

	local function vlist(gap)
		return new("UIListLayout", {
			Padding = UDim.new(0, gap or 6),
			SortOrder = Enum.SortOrder.LayoutOrder,
			FillDirection = Enum.FillDirection.Vertical,
		})
	end

	local function hlist(gap, align)
		return new("UIListLayout", {
			Padding = UDim.new(0, gap or 6),
			SortOrder = Enum.SortOrder.LayoutOrder,
			FillDirection = Enum.FillDirection.Horizontal,
			VerticalAlignment = Enum.VerticalAlignment.Center,
			HorizontalAlignment = align or Enum.HorizontalAlignment.Left,
		})
	end
	UI.corner, UI.stroke, UI.padding, UI.vlist, UI.hlist = corner, stroke, padding, vlist, hlist

	local function tween(inst, props, duration)
		if not inst or not inst.Parent then
			return
		end
		if not Config:get("animations") then
			for k, v in pairs(props) do
				inst[k] = v
			end
			return
		end
		local ok = pcall(function()
			TweenService:Create(inst, TweenInfo.new(duration or 0.18, Enum.EasingStyle.Quint, Enum.EasingDirection.Out), props):Play()
		end)
		if not ok then
			for k, v in pairs(props) do
				inst[k] = v
			end
		end
	end
	UI.tween = tween

	local function hex(c)
		return ("#%02X%02X%02X"):format(math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5))
	end
	UI.hex = hex

	local function escapeRich(s)
		return (tostring(s):gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
	end
	UI.escapeRich = escapeRich

	-- Normalise un texte pour la recherche (minuscules, sans accents).
	local ACCENTS = {
		["à"] = "a", ["â"] = "a", ["ä"] = "a", ["é"] = "e", ["è"] = "e", ["ê"] = "e", ["ë"] = "e",
		["î"] = "i", ["ï"] = "i", ["ô"] = "o", ["ö"] = "o", ["ù"] = "u", ["û"] = "u", ["ü"] = "u", ["ç"] = "c",
		["À"] = "a", ["Â"] = "a", ["É"] = "e", ["È"] = "e", ["Ê"] = "e", ["Î"] = "i", ["Ô"] = "o", ["Ç"] = "c",
	}
	local function normalize(s)
		s = string.lower(tostring(s or ""))
		for from, to in pairs(ACCENTS) do
			s = s:gsub(from, to)
		end
		return s
	end
	UI.normalize = normalize

	local function hover(button, base, over)
		Tasks:connect(button.MouseEnter, function()
			tween(button, { BackgroundColor3 = over }, 0.12)
		end, "survol")
		Tasks:connect(button.MouseLeave, function()
			tween(button, { BackgroundColor3 = base }, 0.12)
		end, "survol")
	end

	-- Clic protégé + anti double clic.
	local function onClick(button, fn, label)
		local last = 0
		Tasks:connect(button.MouseButton1Click, function()
			local t = now()
			if t - last < 0.25 then
				return
			end
			last = t
			fn()
		end, label or "clic")
	end
	UI.onClick = onClick

	---------------------------------------------------------------------------
	-- Construction de la fenêtre
	---------------------------------------------------------------------------

	local function parentGui(gui)
		if Compat.hui then
			local ok = pcall(function()
				gui.Parent = Compat.hui
			end)
			if ok and gui.Parent then
				return "gethui"
			end
		end
		if Compat:has("coregui") then
			local ok = pcall(function()
				gui.Parent = game:GetService("CoreGui")
			end)
			if ok and gui.Parent then
				return "CoreGui"
			end
		end
		local pg = Players.LocalPlayer:FindFirstChildOfClass("PlayerGui") or Players.LocalPlayer:WaitForChild("PlayerGui", 10)
		gui.Parent = pg
		return "PlayerGui"
	end

	-- Supprime une ancienne interface restée en place (instance précédente plantée).
	local function removeOld()
		local places = { Compat.hui }
		pcall(function()
			table.insert(places, game:GetService("CoreGui"))
		end)
		local pg = Players.LocalPlayer:FindFirstChildOfClass("PlayerGui")
		if pg then
			table.insert(places, pg)
		end
		for _, place in ipairs(places) do
			if place then
				pcall(function()
					for _, child in ipairs(place:GetChildren()) do
						if child.Name == GUI_NAME then
							child:Destroy()
						end
					end
				end)
			end
		end
	end

	removeOld()

	local gui = new("ScreenGui", {
		Name = GUI_NAME,
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		DisplayOrder = 50,
	})
	if type(syn) == "table" and type(syn.protect_gui) == "function" then
		pcall(syn.protect_gui, gui)
	end
	UI.gui = gui
	UI.parentMode = parentGui(gui)
	Diag:info("Interface attachée à " .. UI.parentMode)

	local window = new("Frame", {
		Name = "Window",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, Config:get("windowX"), 0.5, Config:get("windowY")),
		Size = UDim2.fromOffset(WIN_W, WIN_H),
		BackgroundColor3 = Theme.bg,
		BorderSizePixel = 0,
		ClipsDescendants = true,
		Parent = gui,
	}, { corner(12), stroke(Theme.stroke, 1) })
	local scale = new("UIScale", { Scale = Config:get("uiScale"), Parent = window })
	UI.window, UI.scale = window, scale

	-- Barre de titre
	local titleBar = new("Frame", {
		Name = "TitleBar",
		Size = UDim2.new(1, 0, 0, TITLE_H),
		BackgroundTransparency = 1,
		Parent = window,
	})
	new("TextLabel", {
		Text = "◆",
		Font = Theme.fontBold,
		TextSize = 18,
		TextColor3 = Theme.accent,
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(16, 0),
		Size = UDim2.new(0, 18, 1, 0),
		Parent = titleBar,
	})
	new("TextLabel", {
		Text = "BloxHub",
		Font = Theme.fontBold,
		TextSize = 15,
		TextColor3 = Theme.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(40, 0),
		Size = UDim2.new(0, 80, 1, 0),
		Parent = titleBar,
	})
	new("TextLabel", {
		Text = "v" .. Hub.Version .. "  ·  Blox Fruits",
		Font = Theme.font,
		TextSize = 12,
		TextColor3 = Theme.muted,
		TextXAlignment = Enum.TextXAlignment.Left,
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(112, 0),
		Size = UDim2.new(0, 200, 1, 0),
		Parent = titleBar,
	})

	local function titleButton(text, x, hoverColor)
		local b = new("TextButton", {
			Text = text,
			Font = Theme.fontBold,
			TextSize = 16,
			TextColor3 = Theme.muted,
			AutoButtonColor = false,
			BackgroundColor3 = Theme.bg,
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, x, 0.5, 0),
			Size = UDim2.fromOffset(30, 26),
			Parent = titleBar,
		}, { corner(7) })
		hover(b, Theme.bg, hoverColor)
		return b
	end
	local closeBtn = titleButton("×", -12, Color3.fromRGB(90, 30, 40))
	local minBtn = titleButton("–", -48, Theme.cardHover)

	new("Frame", {
		Name = "Separator",
		BackgroundColor3 = Theme.stroke,
		BorderSizePixel = 0,
		Position = UDim2.fromOffset(0, TITLE_H),
		Size = UDim2.new(1, 0, 0, 1),
		Parent = window,
	})

	local body = new("Frame", {
		Name = "Body",
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(0, TITLE_H + 1),
		Size = UDim2.new(1, 0, 1, -(TITLE_H + 1)),
		Parent = window,
	})
	UI.body = body

	-- Barre latérale
	local sidebar = new("Frame", {
		Name = "Sidebar",
		BackgroundColor3 = Theme.panel,
		BorderSizePixel = 0,
		Size = UDim2.new(0, SIDEBAR_W, 1, 0),
		Parent = body,
	})
	local searchBox = new("TextBox", {
		Name = "Search",
		PlaceholderText = "🔍  Rechercher…",
		PlaceholderColor3 = Theme.muted,
		Text = "",
		ClearTextOnFocus = false,
		Font = Theme.font,
		TextSize = 13,
		TextColor3 = Theme.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		BackgroundColor3 = Theme.input,
		Position = UDim2.fromOffset(10, 10),
		Size = UDim2.new(1, -20, 0, 32),
		Parent = sidebar,
	}, { corner(8), stroke(Theme.stroke, 1), padding(0, 10, 0, 10) })
	UI.searchBox = searchBox

	local nav = new("ScrollingFrame", {
		Name = "Nav",
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Position = UDim2.fromOffset(0, 52),
		Size = UDim2.new(1, 0, 1, -82),
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		ScrollBarThickness = 2,
		ScrollBarImageColor3 = Theme.accent,
		Parent = sidebar,
	}, { vlist(4), padding(0, 10, 6, 10) })

	new("TextLabel", {
		Name = "Footer",
		Text = "Aucune automatisation · lecture seule",
		Font = Theme.font,
		TextSize = 10,
		TextColor3 = Theme.unknown,
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 0, 1, -8),
		Size = UDim2.new(1, 0, 0, 18),
		Parent = sidebar,
	})

	-- Zone de contenu
	local content = new("Frame", {
		Name = "Content",
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(SIDEBAR_W, 0),
		Size = UDim2.new(1, -SIDEBAR_W, 1, 0),
		Parent = body,
	})
	local header = new("Frame", {
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(18, 10),
		Size = UDim2.new(1, -36, 0, 42),
		Parent = content,
	})
	local headerTitle = new("TextLabel", {
		Text = "",
		Font = Theme.fontBold,
		TextSize = 18,
		TextColor3 = Theme.text,
		TextXAlignment = Enum.TextXAlignment.Left,
		BackgroundTransparency = 1,
		Size = UDim2.new(1, 0, 0, 22),
		Parent = header,
	})
	local headerSub = new("TextLabel", {
		Text = "",
		Font = Theme.font,
		TextSize = 12,
		TextColor3 = Theme.muted,
		TextXAlignment = Enum.TextXAlignment.Left,
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(0, 22),
		Size = UDim2.new(1, 0, 0, 18),
		Parent = header,
	})
	local pagesHolder = new("Frame", {
		Name = "Pages",
		BackgroundTransparency = 1,
		ClipsDescendants = true,
		Position = UDim2.fromOffset(12, 58),
		Size = UDim2.new(1, -18, 1, -64),
		Parent = content,
	})

	-- Bouton flottant de réouverture
	local reopen = new("TextButton", {
		Name = "Reopen",
		Text = "◆  BloxHub",
		Font = Theme.fontBold,
		TextSize = 13,
		TextColor3 = Theme.text,
		AutoButtonColor = false,
		BackgroundColor3 = Theme.bg,
		Position = UDim2.fromOffset(14, 70),
		Size = UDim2.fromOffset(112, 34),
		Visible = false,
		Parent = gui,
	}, { corner(17), stroke(Theme.accent, 1) })
	hover(reopen, Theme.bg, Theme.accentSoft)
	UI.reopenButton = reopen

	---------------------------------------------------------------------------
	-- Déplacement (fenêtre et bouton flottant), borné à l'écran
	---------------------------------------------------------------------------

	local function viewport()
		local cam = workspace.CurrentCamera
		return cam and cam.ViewportSize or Vector2.new(1280, 720)
	end

	-- La position est celle du bord haut-centre de la fenêtre par rapport au centre de l'écran.
	-- On garde toujours la barre de titre visible.
	local function clampWindow()
		local vp = viewport()
		local s = scale.Scale
		local w = WIN_W * s
		local maxX = math.max(0, vp.X / 2 + w / 2 - 80)
		local minY = -vp.Y / 2
		local maxY = math.max(minY, vp.Y / 2 - TITLE_H * s)
		local p = window.Position
		local x = math.clamp(p.X.Offset, -maxX, maxX)
		local y = math.clamp(p.Y.Offset, minY, maxY)
		window.Position = UDim2.new(0.5, x, 0.5, y)
		return x, y
	end
	UI.clampWindow = clampWindow

	local drag
	local function startDrag(target, input, onEnd)
		drag = { target = target, start = input.Position, origin = target.Position, onEnd = onEnd, moved = false }
	end

	Tasks:connect(titleBar.InputBegan, function(input)
		if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
			startDrag(window, input, function()
				local x, y = clampWindow()
				Config:set("windowX", math.floor(x))
				Config:set("windowY", math.floor(y))
			end)
		end
	end, "drag fenêtre")

	Tasks:connect(reopen.InputBegan, function(input)
		if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
			startDrag(reopen, input)
		end
	end, "drag bouton")

	Tasks:connect(UserInputService.InputChanged, function(input)
		if not drag then
			return
		end
		if input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then
			local delta = input.Position - drag.start
			if math.abs(delta.X) + math.abs(delta.Y) > 3 then
				drag.moved = true
			end
			local o = drag.origin
			drag.target.Position = UDim2.new(o.X.Scale, o.X.Offset + delta.X, o.Y.Scale, o.Y.Offset + delta.Y)
		end
	end, "drag déplacement")

	Tasks:connect(UserInputService.InputEnded, function(input)
		if drag and (input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch) then
			local d = drag
			drag = nil
			UI.lastDragMoved = d.moved
			if d.onEnd then
				d.onEnd()
			end
		end
	end, "drag fin")

	---------------------------------------------------------------------------
	-- Visibilité : réduire, masquer, rouvrir
	---------------------------------------------------------------------------

	local visibilityListeners = {}
	function UI:onVisibility(fn)
		table.insert(visibilityListeners, fn)
	end
	local function fireVisibility()
		local shown = UI.visible and not UI.minimized
		for _, fn in ipairs(visibilityListeners) do
			Diag:safe("visibilité", fn, shown)
		end
		if UI.current then
			local page = UI.pages[UI.current]
			if shown and page.onShow then
				Diag:safe("affichage " .. page.id, page.onShow)
			elseif not shown and page.onHide then
				Diag:safe("masquage " .. page.id, page.onHide)
			end
		end
	end

	function UI:setMinimized(state)
		if self.minimized == state then
			return
		end
		self.minimized = state
		minBtn.Text = state and "▢" or "–"
		if state then
			body.Visible = false
			tween(window, { Size = UDim2.fromOffset(WIN_W, TITLE_H) }, 0.2)
		else
			tween(window, { Size = UDim2.fromOffset(WIN_W, WIN_H) }, 0.2)
			body.Visible = true
		end
		clampWindow()
		fireVisibility()
	end

	function UI:setVisible(state)
		if self.visible == state then
			return
		end
		self.visible = state
		window.Visible = state
		reopen.Visible = not state
		if state then
			clampWindow()
		end
		fireVisibility()
	end

	function UI:toggle()
		self:setVisible(not self.visible)
	end

	onClick(minBtn, function()
		UI:setMinimized(not UI.minimized)
	end, "réduire")
	onClick(closeBtn, function()
		UI:setVisible(false)
		Hub.notify("BloxHub masqué", "Clique sur ◆ BloxHub ou appuie sur " .. Config:get("toggleKey") .. " pour le rouvrir.", "info", 4)
	end, "masquer")
	onClick(reopen, function()
		if UI.lastDragMoved or (drag and drag.moved) then
			UI.lastDragMoved = false
			return
		end
		UI:setVisible(true)
	end, "rouvrir")

	Tasks:connect(UserInputService.InputBegan, function(input, processed)
		if processed or UserInputService:GetFocusedTextBox() then
			return
		end
		local ok, key = pcall(function()
			return Enum.KeyCode[Config:get("toggleKey")]
		end)
		if ok and key and input.KeyCode == key then
			UI:toggle()
		end
	end, "raccourci")

	-- Si l'interface est retirée par autre chose que le hub, on la rattache une fois.
	local reattached = false
	Tasks:connect(gui.AncestryChanged, function(_, parent)
		if parent == nil and Hub.Running and not UI.destroying and not reattached then
			reattached = true
			Diag:warn("Interface détachée de façon inattendue : rattachement")
			task.defer(function()
				if Hub.Running then
					pcall(parentGui, gui)
				end
			end)
		end
	end, "surveillance gui")

	Config:onChange(function(key, value)
		if key == "uiScale" then
			scale.Scale = value
			clampWindow()
		end
	end)

	---------------------------------------------------------------------------
	-- Pages et navigation
	---------------------------------------------------------------------------

	local function setNavSelected(page, selected)
		local nb = page.navButton
		tween(nb, { BackgroundColor3 = selected and Theme.accentSoft or Theme.panel }, 0.15)
		nb.Indicator.Visible = selected
		nb.Label.TextColor3 = selected and Theme.text or Theme.muted
	end

	-- opts : { title, subtitle, icon, order, hidden, onShow, onHide }
	function UI:addPage(id, opts)
		assert(not self.pages[id], "page déjà déclarée : " .. tostring(id))
		local frame = new("ScrollingFrame", {
			Name = "Page_" .. id,
			BackgroundTransparency = 1,
			BorderSizePixel = 0,
			Size = UDim2.fromScale(1, 1),
			CanvasSize = UDim2.new(),
			AutomaticCanvasSize = Enum.AutomaticSize.Y,
			ScrollBarThickness = 3,
			ScrollBarImageColor3 = Theme.accent,
			ScrollingDirection = Enum.ScrollingDirection.Y,
			Visible = false,
			Parent = pagesHolder,
		}, { vlist(8), padding(4, 10, 12, 6) })

		local page = {
			id = id,
			title = opts.title,
			subtitle = opts.subtitle or "",
			frame = frame,
			onShow = opts.onShow,
			onHide = opts.onHide,
			order = opts.order or (#self.pageList + 1),
		}

		if not opts.hidden then
			local nb = new("TextButton", {
				Name = "Nav_" .. id,
				Text = "",
				AutoButtonColor = false,
				BackgroundColor3 = Theme.panel,
				Size = UDim2.new(1, 0, 0, 34),
				LayoutOrder = page.order,
				Parent = nav,
			}, { corner(8) })
			new("Frame", {
				Name = "Indicator",
				BackgroundColor3 = Theme.accent,
				BorderSizePixel = 0,
				Position = UDim2.new(0, 0, 0.5, -8),
				Size = UDim2.fromOffset(3, 16),
				Visible = false,
				Parent = nb,
			}, { corner(2) })
			new("TextLabel", {
				Name = "Icon",
				Text = opts.icon or "•",
				Font = Theme.font,
				TextSize = 15,
				TextColor3 = Theme.text,
				BackgroundTransparency = 1,
				Position = UDim2.fromOffset(10, 0),
				Size = UDim2.new(0, 22, 1, 0),
				Parent = nb,
			})
			new("TextLabel", {
				Name = "Label",
				Text = opts.title,
				Font = Theme.fontMedium,
				TextSize = 13,
				TextColor3 = Theme.muted,
				TextXAlignment = Enum.TextXAlignment.Left,
				BackgroundTransparency = 1,
				Position = UDim2.fromOffset(38, 0),
				Size = UDim2.new(1, -42, 1, 0),
				Parent = nb,
			})
			Tasks:connect(nb.MouseEnter, function()
				if UI.current ~= id then
					tween(nb, { BackgroundColor3 = Theme.card }, 0.12)
				end
			end, "survol nav")
			Tasks:connect(nb.MouseLeave, function()
				if UI.current ~= id then
					tween(nb, { BackgroundColor3 = Theme.panel }, 0.12)
				end
			end, "survol nav")
			onClick(nb, function()
				if searchBox.Text ~= "" then
					searchBox.Text = ""
				end
				UI:select(id)
			end, "navigation " .. id)
			page.navButton = nb
		end

		self.pages[id] = page
		table.insert(self.pageList, page)
		self:addSearch(opts.title, opts.subtitle or "", id, nil)
		return page
	end

	-- Titre de groupe dans la barre latérale (SUIVI, AUTOMATISATION, OUTILS).
	function UI:addNavHeader(text, layoutOrder)
		return new("TextLabel", {
			Name = "Header_" .. text,
			Text = text,
			Font = Theme.fontBold,
			TextSize = 10,
			TextColor3 = Theme.unknown,
			TextXAlignment = Enum.TextXAlignment.Left,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 22),
			LayoutOrder = layoutOrder,
			Parent = nav,
		}, { padding(8, 0, 0, 10) })
	end
	UI:addNavHeader("SUIVI", 5)
	UI:addNavHeader("AUTOMATISATION", 55)
	UI:addNavHeader("OUTILS", 75)

	function UI:select(id)
		local page = self.pages[id]
		if not page then
			return false
		end
		if self.current == id then
			return true
		end
		local previous = self.current and self.pages[self.current]
		if previous then
			previous.frame.Visible = false
			if previous.navButton then
				setNavSelected(previous, false)
			end
			if previous.onHide then
				Diag:safe("masquage " .. previous.id, previous.onHide)
			end
		end
		self.current = id
		headerTitle.Text = page.title
		headerSub.Text = page.subtitle
		page.frame.Visible = true
		page.frame.Position = UDim2.fromOffset(0, 10)
		tween(page.frame, { Position = UDim2.fromOffset(0, 0) }, 0.2)
		if page.navButton then
			setNavSelected(page, true)
			if id ~= "search" then
				Config:set("lastPage", id)
			end
		end
		if page.onShow and self.visible and not self.minimized then
			Diag:safe("affichage " .. id, page.onShow)
		end
		return true
	end

	---------------------------------------------------------------------------
	-- Recherche
	---------------------------------------------------------------------------

	function UI:addSearch(title, keywords, pageId, target)
		table.insert(self.searchIndex, {
			title = title,
			key = normalize(title .. " " .. (keywords or "")),
			page = pageId,
			target = target,
		})
	end

	function UI:scrollTo(pageId, target)
		local page = self.pages[pageId]
		if not page or not target or not target.Parent then
			return
		end
		task.defer(function()
			local f = page.frame
			local y = target.AbsolutePosition.Y - f.AbsolutePosition.Y + f.CanvasPosition.Y - 6
			f.CanvasPosition = Vector2.new(0, math.max(0, y))
			local s = target:FindFirstChildOfClass("UIStroke")
			if s then
				s.Color = Theme.accent
				task.delay(1.2, function()
					if s.Parent then
						tween(s, { Color = Theme.stroke }, 0.4)
					end
				end)
			end
		end)
	end

	local searchPage = UI:addPage("search", { title = "Recherche", subtitle = "Résultats", hidden = true })
	table.remove(UI.searchIndex) -- la page de recherche ne doit pas apparaître dans ses propres résultats
	local returnPage

	local function runSearch(query)
		for _, child in ipairs(searchPage.frame:GetChildren()) do
			if child:IsA("GuiObject") then
				child:Destroy()
			end
		end
		local q = normalize(query)
		local results = {}
		for _, entry in ipairs(UI.searchIndex) do
			if entry.key:find(q, 1, true) then
				table.insert(results, entry)
				if #results >= 40 then
					break
				end
			end
		end
		searchPage.subtitle = #results .. " résultat(s) pour « " .. query .. " »"
		headerSub.Text = searchPage.subtitle
		if #results == 0 then
			UI.c.label(searchPage.frame, "Aucun résultat. Essaie « saber », « fragments », « v3 »…", { muted = true })
			return
		end
		for _, entry in ipairs(results) do
			local pageTitle = UI.pages[entry.page] and UI.pages[entry.page].title or entry.page
			UI.c.button(searchPage.frame, entry.title .. "   ·   " .. pageTitle, function()
				searchBox.Text = ""
				UI:select(entry.page)
				UI:scrollTo(entry.page, entry.target)
			end, { align = "left" })
		end
	end
	UI.runSearch = runSearch

	local searchToken = 0
	Tasks:connect(searchBox:GetPropertyChangedSignal("Text"), function()
		searchToken += 1
		local my = searchToken
		local text = searchBox.Text
		if text == "" then
			if UI.current == "search" then
				UI:select(returnPage or "dashboard")
			end
			return
		end
		if UI.current ~= "search" then
			returnPage = UI.current
		end
		task.delay(0.2, function()
			if my ~= searchToken or not Hub.Running then
				return
			end
			UI:select("search")
			Diag:safe("recherche", runSearch, text)
		end)
	end, "recherche")

	---------------------------------------------------------------------------
	-- Composants
	---------------------------------------------------------------------------

	local c = {}
	UI.c = c

	function c.section(parent, text)
		return new("TextLabel", {
			Text = string.upper(text),
			Font = Theme.fontBold,
			TextSize = 11,
			TextColor3 = Theme.accent,
			TextXAlignment = Enum.TextXAlignment.Left,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 22),
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, { padding(6, 0, 0, 2) })
	end

	function c.card(parent, opts)
		opts = opts or {}
		return new("Frame", {
			BackgroundColor3 = opts.color or Theme.card,
			BorderSizePixel = 0,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, { corner(10), stroke(Theme.stroke, 1), padding(opts.pad or 12), vlist(opts.gap or 6) })
	end

	function c.label(parent, text, opts)
		opts = opts or {}
		return new("TextLabel", {
			Text = text,
			RichText = opts.rich or false,
			Font = opts.bold and Theme.fontBold or (opts.medium and Theme.fontMedium or Theme.font),
			TextSize = opts.size or 13,
			TextColor3 = opts.color or (opts.muted and Theme.muted or Theme.text),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextYAlignment = Enum.TextYAlignment.Top,
			TextWrapped = true,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			LayoutOrder = nextOrder(),
			Parent = parent,
		})
	end

	-- opts : { accent, danger, align, width }
	function c.button(parent, text, fn, opts)
		opts = opts or {}
		local base = opts.accent and Theme.accent or (opts.danger and Color3.fromRGB(110, 34, 46) or Theme.cardHover)
		local over = opts.accent and Color3.fromRGB(157, 116, 250) or (opts.danger and Color3.fromRGB(140, 44, 58) or Color3.fromRGB(44, 44, 60))
		local b = new("TextButton", {
			Text = text,
			Font = Theme.fontMedium,
			TextSize = 13,
			TextColor3 = Theme.text,
			TextXAlignment = opts.align == "left" and Enum.TextXAlignment.Left or Enum.TextXAlignment.Center,
			TextTruncate = Enum.TextTruncate.AtEnd,
			AutoButtonColor = false,
			BackgroundColor3 = base,
			Size = opts.width and UDim2.fromOffset(opts.width, 32) or UDim2.new(1, 0, 0, 32),
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, { corner(8), padding(0, 12, 0, 12) })
		hover(b, base, over)
		onClick(b, fn, "bouton " .. text)
		return b
	end

	-- Rangée horizontale de boutons.
	function c.row(parent, height)
		return new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, height or 32),
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, { hlist(8) })
	end

	function c.toggle(parent, text, value, fn, desc)
		local state = value and true or false
		local row = new("TextButton", {
			Text = "",
			AutoButtonColor = false,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, desc and 44 or 32),
			LayoutOrder = nextOrder(),
			Parent = parent,
		})
		new("TextLabel", {
			Text = text,
			Font = Theme.fontMedium,
			TextSize = 13,
			TextColor3 = Theme.text,
			TextXAlignment = Enum.TextXAlignment.Left,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, -60, 0, desc and 22 or 32),
			Parent = row,
		})
		if desc then
			new("TextLabel", {
				Text = desc,
				Font = Theme.font,
				TextSize = 11,
				TextColor3 = Theme.muted,
				TextXAlignment = Enum.TextXAlignment.Left,
				TextTruncate = Enum.TextTruncate.AtEnd,
				BackgroundTransparency = 1,
				Position = UDim2.fromOffset(0, 22),
				Size = UDim2.new(1, -60, 0, 18),
				Parent = row,
			})
		end
		local track = new("Frame", {
			Name = "Track",
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, 0, 0.5, 0),
			Size = UDim2.fromOffset(40, 22),
			BackgroundColor3 = state and Theme.accent or Theme.stroke,
			Parent = row,
		}, { corner(11) })
		local knob = new("Frame", {
			Name = "Knob",
			AnchorPoint = Vector2.new(0, 0.5),
			Position = UDim2.new(0, state and 21 or 3, 0.5, 0),
			Size = UDim2.fromOffset(16, 16),
			BackgroundColor3 = Theme.text,
			Parent = track,
		}, { corner(8) })
		local api = {}
		function api.set(v, silent)
			state = v and true or false
			tween(track, { BackgroundColor3 = state and Theme.accent or Theme.stroke }, 0.15)
			tween(knob, { Position = UDim2.new(0, state and 21 or 3, 0.5, 0) }, 0.15)
			if not silent and fn then
				fn(state)
			end
		end
		function api.get()
			return state
		end
		api.instance = row
		onClick(row, function()
			api.set(not state)
		end, "interrupteur " .. text)
		return api
	end

	-- Sélecteur cyclique : options = { {label=..., value=...}, ... }
	function c.choice(parent, text, options, current, fn)
		local idx = 1
		for i, o in ipairs(options) do
			if o.value == current then
				idx = i
			end
		end
		local row = new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 32),
			LayoutOrder = nextOrder(),
			Parent = parent,
		})
		new("TextLabel", {
			Text = text,
			Font = Theme.fontMedium,
			TextSize = 13,
			TextColor3 = Theme.text,
			TextXAlignment = Enum.TextXAlignment.Left,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, -130, 1, 0),
			Parent = row,
		})
		local b = new("TextButton", {
			Text = options[idx].label .. "  ▸",
			Font = Theme.fontMedium,
			TextSize = 12,
			TextColor3 = Theme.text,
			AutoButtonColor = false,
			BackgroundColor3 = Theme.cardHover,
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, 0, 0.5, 0),
			Size = UDim2.fromOffset(120, 28),
			Parent = row,
		}, { corner(7) })
		hover(b, Theme.cardHover, Color3.fromRGB(44, 44, 60))
		local api = { instance = row, button = b }
		function api.get()
			return options[idx].value
		end
		onClick(b, function()
			idx = idx % #options + 1
			b.Text = options[idx].label .. "  ▸"
			if fn then
				fn(options[idx].value)
			end
		end, "choix " .. text)
		return api
	end

	-- Barre de progression ; renvoie set(ratio, rightText, leftText).
	function c.progress(parent, text, ratio, rightText, color)
		local holder = new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 30),
			LayoutOrder = nextOrder(),
			Parent = parent,
		})
		local left = new("TextLabel", {
			Text = text,
			Font = Theme.fontMedium,
			TextSize = 12,
			TextColor3 = Theme.text,
			TextXAlignment = Enum.TextXAlignment.Left,
			TextTruncate = Enum.TextTruncate.AtEnd,
			BackgroundTransparency = 1,
			Size = UDim2.new(0.62, 0, 0, 16),
			Parent = holder,
		})
		local right = new("TextLabel", {
			Text = rightText or "",
			Font = Theme.font,
			TextSize = 12,
			TextColor3 = Theme.muted,
			TextXAlignment = Enum.TextXAlignment.Right,
			BackgroundTransparency = 1,
			Position = UDim2.fromScale(0.62, 0),
			Size = UDim2.new(0.38, 0, 0, 16),
			Parent = holder,
		})
		local bar = new("Frame", {
			BackgroundColor3 = Theme.input,
			BorderSizePixel = 0,
			Position = UDim2.fromOffset(0, 20),
			Size = UDim2.new(1, 0, 0, 6),
			Parent = holder,
		}, { corner(3) })
		local fill = new("Frame", {
			BackgroundColor3 = color or Theme.accent,
			BorderSizePixel = 0,
			Size = UDim2.fromScale(math.clamp(ratio or 0, 0, 1), 1),
			Parent = bar,
		}, { corner(3) })
		local function set(r, rt, lt)
			r = math.clamp(tonumber(r) or 0, 0, 1)
			tween(fill, { Size = UDim2.fromScale(r, 1) }, 0.25)
			fill.BackgroundColor3 = r >= 1 and Theme.ok or (color or Theme.accent)
			if rt then
				right.Text = rt
			end
			if lt then
				left.Text = lt
			end
		end
		set(ratio or 0)
		return set, holder
	end

	-- Ligne d'état : status = "ok" | "missing" | "unknown" | "warn"
	local STATUS = {
		ok = { "✓", Theme.ok },
		missing = { "✗", Theme.bad },
		unknown = { "?", Theme.unknown },
		warn = { "!", Theme.warn },
	}
	UI.STATUS = STATUS

	function c.status(parent, status, text, detail)
		local s = STATUS[status] or STATUS.unknown
		local row = new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			LayoutOrder = nextOrder(),
			Parent = parent,
		})
		new("TextLabel", {
			Text = s[1],
			Font = Theme.fontBold,
			TextSize = 13,
			TextColor3 = s[2],
			BackgroundTransparency = 1,
			Size = UDim2.fromOffset(16, 16),
			Parent = row,
		})
		local label = new("TextLabel", {
			Text = detail and (escapeRich(text) .. '  <font color="' .. hex(Theme.muted) .. '">' .. escapeRich(detail) .. "</font>") or escapeRich(text),
			RichText = true,
			Font = Theme.font,
			TextSize = 13,
			TextColor3 = Theme.text,
			TextXAlignment = Enum.TextXAlignment.Left,
			TextYAlignment = Enum.TextYAlignment.Top,
			TextWrapped = true,
			BackgroundTransparency = 1,
			Position = UDim2.fromOffset(22, 0),
			Size = UDim2.new(1, -22, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			Parent = row,
		})
		return row, label
	end

	-- Grille de tuiles statistiques ; renvoie une fonction tile(title, value) -> setter.
	function c.grid(parent, columns, height)
		local grid = new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, {
			new("UIGridLayout", {
				CellPadding = UDim2.fromOffset(8, 8),
				CellSize = UDim2.new(1 / (columns or 2), -8, 0, height or 62),
				SortOrder = Enum.SortOrder.LayoutOrder,
			}),
		})
		local function tile(title, value)
			local t = new("Frame", {
				BackgroundColor3 = Theme.card,
				BorderSizePixel = 0,
				LayoutOrder = nextOrder(),
				Parent = grid,
			}, { corner(10), stroke(Theme.stroke, 1), padding(10, 12, 10, 12) })
			new("TextLabel", {
				Text = title,
				Font = Theme.font,
				TextSize = 11,
				TextColor3 = Theme.muted,
				TextXAlignment = Enum.TextXAlignment.Left,
				BackgroundTransparency = 1,
				Size = UDim2.new(1, 0, 0, 14),
				Parent = t,
			})
			local v = new("TextLabel", {
				Name = "Value",
				Text = value or "—",
				Font = Theme.fontBold,
				TextSize = 16,
				TextColor3 = Theme.text,
				TextXAlignment = Enum.TextXAlignment.Left,
				TextTruncate = Enum.TextTruncate.AtEnd,
				BackgroundTransparency = 1,
				Position = UDim2.fromOffset(0, 18),
				Size = UDim2.new(1, 0, 0, 22),
				Parent = t,
			})
			return function(text, color)
				v.Text = text
				v.TextColor3 = color or Theme.text
			end, t
		end
		return tile, grid
	end

	-- Carte repliable construite à la demande (build(body) appelé à chaque ouverture).
	function c.collapsible(parent, title, subtitle, build, opts)
		opts = opts or {}
		local cardFrame = new("Frame", {
			BackgroundColor3 = Theme.card,
			BorderSizePixel = 0,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			LayoutOrder = nextOrder(),
			Parent = parent,
		}, { corner(10), stroke(Theme.stroke, 1), vlist(0) })
		local head = new("TextButton", {
			Text = "",
			AutoButtonColor = false,
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 52),
			LayoutOrder = 1,
			Parent = cardFrame,
		})
		new("TextLabel", {
			Text = opts.icon or "•",
			Font = Theme.font,
			TextSize = 18,
			TextColor3 = Theme.text,
			BackgroundTransparency = 1,
			Position = UDim2.fromOffset(12, 0),
			Size = UDim2.new(0, 26, 1, 0),
			Parent = head,
		})
		local titleLabel = new("TextLabel", {
			Text = title,
			Font = Theme.fontBold,
			TextSize = 14,
			TextColor3 = Theme.text,
			TextXAlignment = Enum.TextXAlignment.Left,
			BackgroundTransparency = 1,
			Position = UDim2.fromOffset(46, 8),
			Size = UDim2.new(1, -150, 0, 18),
			Parent = head,
		})
		local subLabel = new("TextLabel", {
			Text = subtitle or "",
			Font = Theme.font,
			TextSize = 11,
			TextColor3 = Theme.muted,
			TextXAlignment = Enum.TextXAlignment.Left,
			TextTruncate = Enum.TextTruncate.AtEnd,
			BackgroundTransparency = 1,
			Position = UDim2.fromOffset(46, 27),
			Size = UDim2.new(1, -150, 0, 16),
			Parent = head,
		})
		local badge = new("TextLabel", {
			Name = "Badge",
			Text = opts.badge or "",
			Font = Theme.fontBold,
			TextSize = 11,
			TextColor3 = Theme.text,
			BackgroundColor3 = Theme.accentSoft,
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -36, 0.5, 0),
			Size = UDim2.fromOffset(78, 22),
			Visible = opts.badge ~= nil,
			Parent = head,
		}, { corner(11) })
		local arrow = new("TextLabel", {
			Text = "▸",
			Font = Theme.fontBold,
			TextSize = 14,
			TextColor3 = Theme.muted,
			BackgroundTransparency = 1,
			AnchorPoint = Vector2.new(1, 0.5),
			Position = UDim2.new(1, -10, 0.5, 0),
			Size = UDim2.fromOffset(20, 20),
			Parent = head,
		})
		local bodyFrame = new("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(1, 0, 0, 0),
			AutomaticSize = Enum.AutomaticSize.Y,
			Visible = false,
			LayoutOrder = 2,
			Parent = cardFrame,
		}, { vlist(6), padding(0, 14, 14, 14) })

		local api = { frame = cardFrame, open = false }
		function api.setBadge(text, color)
			badge.Visible = text ~= nil
			badge.Text = text or ""
			badge.BackgroundColor3 = color or Theme.accentSoft
		end
		function api.setSubtitle(text)
			subLabel.Text = text
		end
		function api.rebuild()
			for _, child in ipairs(bodyFrame:GetChildren()) do
				if child:IsA("GuiObject") then
					child:Destroy()
				end
			end
			if build then
				Diag:safe("contenu " .. title, build, bodyFrame, api)
			end
		end
		function api.setOpen(state)
			api.open = state
			arrow.Text = state and "▾" or "▸"
			if state then
				api.rebuild()
			end
			bodyFrame.Visible = state
		end
		onClick(head, function()
			api.setOpen(not api.open)
		end, "carte " .. title)
		api.title = titleLabel
		return api
	end

	---------------------------------------------------------------------------
	-- Démarrage et destruction
	---------------------------------------------------------------------------

	function UI:start()
		table.sort(self.pageList, function(a, b)
			return a.order < b.order
		end)
		local first = Config:get("lastPage")
		if not self.pages[first] or not self.pages[first].navButton then
			first = nil
			for _, p in ipairs(self.pageList) do
				if p.navButton then
					first = p.id
					break
				end
			end
		end
		clampWindow()
		window.Size = UDim2.fromOffset(WIN_W, WIN_H - 16)
		tween(window, { Size = UDim2.fromOffset(WIN_W, WIN_H) }, 0.25)
		if first then
			self:select(first)
		end
	end

	function UI:destroy()
		self.destroying = true
		pcall(function()
			gui:Destroy()
		end)
	end

	return UI
end
