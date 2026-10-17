-- BloxHub / notifications : petites notifications discrètes en bas à droite.

return function(Hub)
	local UI = Hub.Modules.ui
	local Config = Hub.Modules.config
	local Diag = Hub.Modules.diagnostics
	local Theme = UI.Theme
	local new, corner, stroke, padding, vlist = UI.new, UI.corner, UI.stroke, UI.padding, UI.vlist

	local MAX_VISIBLE = 4
	local KIND_COLORS = {
		info = Theme.accent,
		success = Theme.ok,
		warn = Theme.warn,
		error = Theme.bad,
	}

	local Notifications = { items = {} }

	local holder = new("Frame", {
		Name = "Toasts",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, -16, 1, -16),
		Size = UDim2.fromOffset(290, 400),
		Parent = UI.gui,
	}, {
		new("UIListLayout", {
			Padding = UDim.new(0, 8),
			SortOrder = Enum.SortOrder.LayoutOrder,
			VerticalAlignment = Enum.VerticalAlignment.Bottom,
		}),
	})

	local counter = 0

	local function remove(item)
		if item.removed then
			return
		end
		item.removed = true
		for i, it in ipairs(Notifications.items) do
			if it == item then
				table.remove(Notifications.items, i)
				break
			end
		end
		UI.tween(item.inner, { Position = UDim2.fromOffset(310, 0) }, 0.2)
		task.delay(Config:get("animations") and 0.22 or 0, function()
			pcall(function()
				item.slot:Destroy()
			end)
		end)
	end

	function Notifications:push(title, text, kind, duration)
		if not Config:get("notifications") and kind ~= "error" then
			return
		end
		local ok, err = pcall(function()
			counter += 1
			local accent = KIND_COLORS[kind or "info"] or Theme.accent
			local slot = new("Frame", {
				BackgroundTransparency = 1,
				ClipsDescendants = true,
				Size = UDim2.new(1, 0, 0, 0),
				AutomaticSize = Enum.AutomaticSize.Y,
				LayoutOrder = counter,
				Parent = holder,
			})
			local inner = new("Frame", {
				BackgroundColor3 = Theme.panel,
				BorderSizePixel = 0,
				Position = UDim2.fromOffset(310, 0),
				Size = UDim2.new(1, 0, 0, 0),
				AutomaticSize = Enum.AutomaticSize.Y,
				Parent = slot,
			}, { corner(10), stroke(Theme.stroke, 1), padding(10, 12, 10, 16), vlist(2) })
			new("Frame", {
				BackgroundColor3 = accent,
				BorderSizePixel = 0,
				Position = UDim2.new(0, -10, 0, 0),
				Size = UDim2.new(0, 3, 1, 0),
				Parent = inner,
			}, { corner(2) })
			new("TextLabel", {
				Text = tostring(title),
				Font = Theme.fontBold,
				TextSize = 13,
				TextColor3 = Theme.text,
				TextXAlignment = Enum.TextXAlignment.Left,
				TextWrapped = true,
				BackgroundTransparency = 1,
				Size = UDim2.new(1, 0, 0, 0),
				AutomaticSize = Enum.AutomaticSize.Y,
				LayoutOrder = 1,
				Parent = inner,
			})
			if text and text ~= "" then
				new("TextLabel", {
					Text = tostring(text),
					Font = Theme.font,
					TextSize = 12,
					TextColor3 = Theme.muted,
					TextXAlignment = Enum.TextXAlignment.Left,
					TextWrapped = true,
					BackgroundTransparency = 1,
					Size = UDim2.new(1, 0, 0, 0),
					AutomaticSize = Enum.AutomaticSize.Y,
					LayoutOrder = 2,
					Parent = inner,
				})
			end
			local item = { slot = slot, inner = inner }
			table.insert(self.items, item)
			UI.tween(inner, { Position = UDim2.fromOffset(0, 0) }, 0.25)
			while #self.items > MAX_VISIBLE do
				remove(self.items[1])
			end
			task.delay(duration or 4, function()
				remove(item)
			end)
		end)
		if not ok then
			Diag:warn("Notification impossible : " .. tostring(err))
		end
	end

	function Notifications:destroy()
		table.clear(self.items)
		pcall(function()
			holder:Destroy()
		end)
	end

	return Notifications
end
