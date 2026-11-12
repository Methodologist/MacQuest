-- SpeedLevel: quest item button - a click (or keybind / "/click SpeedLevelItemButton") uses the item
-- the current step's quest needs: the Kodo Kombobulator, a torch, a flask to fill...
-- Secure buttons can't change in combat, so changes wait until combat ends.
local _, SL = ...
local QI = {}
SL.QuestItem = QI

local GetItemCount = (C_Item and C_Item.GetItemCount) or GetItemCount
local GetItemSpell = (C_Item and C_Item.GetItemSpell) or GetItemSpell
local GetItemIcon = (C_Item and C_Item.GetItemIconByID) or GetItemIcon

local function usable(id)
    return id and (GetItemCount(id) or 0) > 0 and GetItemSpell and GetItemSpell(id) ~= nil
end

-- the item for a quest: the log's own quest item when the client has one, else our data
local function itemFor(q)
    if not (q and SL.Player:InLog(q)) then return nil end
    if GetQuestLogSpecialItemInfo and C_QuestLog and C_QuestLog.GetLogIndexForQuestID then
        local idx = C_QuestLog.GetLogIndexForQuestID(q)
        local link = idx and GetQuestLogSpecialItemInfo(idx)
        local id = link and tonumber(link:match("item:(%d+)"))
        if usable(id) then return id end
    end
    for _, id in ipairs(SL.QuestItems and SL.QuestItems[q] or {}) do
        if usable(id) then return id end
    end
end

-- the item for what the guide is showing: the current step group first, then the next few steps
function QI:Pick()
    local E = SL.Engine
    local seen, list = {}, {}
    for _, i in ipairs(E:CurrentGroup()) do list[#list + 1] = i end
    for _, i in ipairs(E:Upcoming(4)) do list[#list + 1] = i end
    for _, i in ipairs(list) do
        local st = E.steps[i]
        -- an item that starts the quest: right-click it from the button
        if st and st.t == "A" and st.item and (GetItemCount(st.item) or 0) > 0 then return st.item, st.q end
        if st and st.q and not seen[st.q] and (st.t == "C" or st.t == "T") then
            seen[st.q] = true
            local id = itemFor(st.q)
            if id then return id, st.q end
        end
    end
end

function QI:Init()
    local b = CreateFrame("Button", "SpeedLevelItemButton", UIParent, "SecureActionButtonTemplate")
    b:SetSize(36, 36)
    b:RegisterForClicks("AnyUp", "AnyDown")
    b:SetAttribute("type", "item")
    b.icon = b:CreateTexture(nil, "ARTWORK")
    b.icon:SetAllPoints()
    b.border = b:CreateTexture(nil, "OVERLAY")
    b.border:SetPoint("TOPLEFT", -1, 1)
    b.border:SetPoint("BOTTOMRIGHT", 1, -1)
    b.border:SetColorTexture(1, 0.82, 0.3, 0.6)
    b.border:SetDrawLayer("BACKGROUND")
    b.count = b:CreateFontString(nil, "OVERLAY", "NumberFontNormal")
    b.count:SetPoint("BOTTOMRIGHT", -2, 2)
    b.cd = CreateFrame("Cooldown", nil, b, "CooldownFrameTemplate")
    b.cd:SetAllPoints()
    b:SetHighlightTexture("Interface\\Buttons\\ButtonHilight-Square", "ADD")
    b:SetScript("OnEnter", function(self)
        if not self.itemID then return end
        GameTooltip:SetOwner(self, "ANCHOR_LEFT")
        if GameTooltip.SetItemByID then GameTooltip:SetItemByID(self.itemID) end
        GameTooltip:AddLine("Quest item for: " .. SL.Engine:QuestName(self.questID), 0.5, 0.8, 1)
        GameTooltip:AddLine("Keybind: macro /click SpeedLevelItemButton", 0.6, 0.6, 0.6)
        GameTooltip:Show()
    end)
    b:SetScript("OnLeave", function() GameTooltip:Hide() end)
    b.itemID, b.questID = false, false
    b:Hide()
    self.button = b
    SL:On("BAG_UPDATE_DELAYED", function() QI:Refresh() end)
    SL:On("PLAYER_REGEN_ENABLED", function() if QI.pending then QI:Refresh() end end)
    SL:On("BAG_UPDATE_COOLDOWN", function() QI:UpdateCooldown() end)
end

function QI:UpdateCooldown()
    local b = self.button
    if not (b and b.itemID and b:IsShown()) then return end
    local getcd = (C_Container and C_Container.GetItemCooldown) or GetItemCooldown
    if getcd then
        local start, dur = getcd(b.itemID)
        if start and dur and dur > 0 then b.cd:SetCooldown(start, dur) else b.cd:Clear() end
    end
end

function QI:Refresh()
    if not self.button then
        if not (SL.UI and SL.UI.frame) then return end
        self:Init()
    end
    local b = self.button
    local id, q = nil, nil
    if SL.db.itemButton ~= false and SL.UI.frame:IsShown() then id, q = self:Pick() end
    if InCombatLockdown and InCombatLockdown() then
        self.pending = true          -- secure button: applied when combat ends
        return
    end
    self.pending = false
    if (id or false) ~= b.itemID then
        b:SetAttribute("item", id and ("item:" .. id) or nil)
        b.itemID = id or false
        if id then b.icon:SetTexture(GetItemIcon(id)) end
    end
    b.questID = q or false
    if id then
        b:ClearAllPoints()
        b:SetPoint("TOPRIGHT", SL.UI.frame, "TOPLEFT", -6, -74)
        b:SetScale(SL.db.scale or 1)
        local n = GetItemCount(id) or 0
        b.count:SetText(n > 1 and n or "")
        b:Show()
        self:UpdateCooldown()
    else
        b:Hide()
    end
end
