-- SpeedLevel / Mac Quest - first-run setup window
-- Copyright (C) 2026 Methodologist. GPL-3.0-or-later (see LICENSE).
--
-- Shown once per character (and with /sl setup): route style, dungeon runs and starting zones,
-- picked from cards in the guide's own flat style.  Everything here can be changed later in
-- settings or with slash commands.
local _, SL = ...
local S = {}
SL.Setup = S

local WIDTH = 480
local PAD = 22
local GOLD = { 1.00, 0.82, 0.30 }

local function flat(parent, layer, r, g, b, a)
    local t = parent:CreateTexture(nil, layer)
    t:SetColorTexture(r, g, b, a)
    return t
end

-- 1px border made of four textures (returned so the colour can change on select / hover)
local function border(f, r, g, b, a)
    local edges = {}
    for _, side in ipairs({ "TOP", "BOTTOM", "LEFT", "RIGHT" }) do
        local t = flat(f, "BORDER", r, g, b, a)
        if side == "TOP" or side == "BOTTOM" then
            t:SetHeight(1)
            t:SetPoint(side .. "LEFT")
            t:SetPoint(side .. "RIGHT")
        else
            t:SetWidth(1)
            t:SetPoint("TOP" .. side)
            t:SetPoint("BOTTOM" .. side)
        end
        edges[#edges + 1] = t
    end
    return edges
end

local function setEdges(edges, r, g, b, a)
    for _, t in ipairs(edges) do t:SetColorTexture(r, g, b, a) end
end

local function classColor()
    local file = SL.Player.classFile
    local c = (C_ClassColor and C_ClassColor.GetClassColor and C_ClassColor.GetClassColor(file))
        or (RAID_CLASS_COLORS and RAID_CLASS_COLORS[file])
    if c then return c.r, c.g, c.b end
    return GOLD[1], GOLD[2], GOLD[3]
end

local RACE_LABEL = { NightElf = "Night Elf", Undead = "Undead", Scourge = "Undead" }

-- a selectable option card: icon, title, one or two lines of description, check mark when chosen
local function makeCard(parent, w, h, icon, title, desc, tag)
    local c = CreateFrame("Button", nil, parent)
    c:SetSize(w, h)
    c.bg = flat(c, "BACKGROUND", 1, 1, 1, 0.04)
    c.bg:SetAllPoints()
    c.glow = flat(c, "BACKGROUND", GOLD[1], GOLD[2], GOLD[3], 0)
    c.glow:SetAllPoints()
    c.edges = border(c, 1, 1, 1, 0.10)
    local x = 12
    if icon then
        c.icon = c:CreateTexture(nil, "ARTWORK")
        c.icon:SetSize(30, 30)
        c.icon:SetPoint("TOPLEFT", 10, -10)
        c.icon:SetTexture(icon)
        c.icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
        x = 50
    end
    c.title = c:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    c.title:SetPoint("TOPLEFT", x, -11)
    c.title:SetPoint("RIGHT", -26, 0)
    c.title:SetJustifyH("LEFT")
    c.title:SetWordWrap(true)
    c.title:SetWidth(w - x - 26)          -- set widths: the heights below are known right away
    c.title:SetText(title)
    c.title:SetTextColor(1, 1, 1)
    c.desc = c:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    c.desc:SetPoint("TOPLEFT", c.title, "BOTTOMLEFT", 0, -4)
    c.desc:SetPoint("RIGHT", -10, 0)
    c.desc:SetJustifyH("LEFT")
    c.desc:SetJustifyV("TOP")
    c.desc:SetSpacing(2)
    c.desc:SetWidth(w - x - 10)
    c.desc:SetText(desc or "")
    c.desc:SetTextColor(0.72, 0.72, 0.76)
    if tag then
        c.tag = c:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        c.tag:SetPoint("BOTTOMLEFT", x, 8)
        c.tag:SetText(tag)
        c.tag:SetTextColor(0.45, 0.85, 0.45)
    end
    -- the height this card needs so the title, description and tag never run into each other
    c.need = 11 + math.max(12, c.title:GetStringHeight() or 12) + 4 + (c.desc:GetStringHeight() or 0)
        + (tag and 22 or 0) + 8
    c.check = c:CreateTexture(nil, "OVERLAY")
    c.check:SetSize(20, 20)
    c.check:SetPoint("TOPRIGHT", -6, -6)
    c.check:SetTexture("Interface\\Buttons\\UI-CheckBox-Check")
    c.check:Hide()
    c:SetScript("OnEnter", function(self)
        if not self.selected then self.bg:SetColorTexture(1, 1, 1, 0.08) end
    end)
    c:SetScript("OnLeave", function(self)
        if not self.selected then self.bg:SetColorTexture(1, 1, 1, 0.04) end
    end)
    function c:SetSelected(on)
        self.selected = on
        if on then
            setEdges(self.edges, GOLD[1], GOLD[2], GOLD[3], 0.9)
            self.glow:SetColorTexture(GOLD[1], GOLD[2], GOLD[3], 0.10)
            self.bg:SetColorTexture(1, 1, 1, 0.06)
            self.check:Show()
            self.title:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
        else
            setEdges(self.edges, 1, 1, 1, 0.10)
            self.glow:SetColorTexture(GOLD[1], GOLD[2], GOLD[3], 0)
            self.bg:SetColorTexture(1, 1, 1, 0.04)
            self.check:Hide()
            self.title:SetTextColor(1, 1, 1)
        end
    end
    return c
end

local function sectionLabel(parent, text, y)
    local fs = parent:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    fs:SetPoint("TOPLEFT", PAD, y)
    fs:SetText(text:upper())
    fs:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    local line = flat(parent, "ARTWORK", 1, 1, 1, 0.08)
    line:SetHeight(1)
    line:SetPoint("LEFT", fs, "RIGHT", 8, 0)
    line:SetPoint("RIGHT", parent, "RIGHT", -PAD, 0)
    return fs
end

-- a group of cards where exactly one is chosen
local function choiceRow(parent, y, h, items, chosen, onPick)
    local n = #items
    local gap = 10
    local w = (WIDTH - 2 * PAD - gap * (n - 1)) / n
    local cards = {}
    local function pick(key)
        for _, c in ipairs(cards) do c:SetSelected(c.key == key) end
        onPick(key)
    end
    for k, it in ipairs(items) do
        local c = makeCard(parent, w, h, it.icon, it.title, it.desc, it.tag)
        c:SetPoint("TOPLEFT", PAD + (k - 1) * (w + gap), y)
        c.key = it.key
        c:SetScript("OnClick", function()
            if PlaySound and SOUNDKIT and SOUNDKIT.IG_MAINMENU_OPTION_CHECKBOX_ON then
                PlaySound(SOUNDKIT.IG_MAINMENU_OPTION_CHECKBOX_ON)
            end
            pick(it.key)
        end)
        cards[k] = c
    end
    pick(chosen)
    -- the row is as tall as its tallest card
    local rowH = h
    for _, c in ipairs(cards) do rowH = math.max(rowH, math.ceil(c.need or 0)) end
    for _, c in ipairs(cards) do c:SetHeight(rowH) end
    return rowH, cards
end

local PATH_SHORT = {
    Orc = "Orc / Troll", Tauren = "Tauren", Undead = "Undead", Human = "Human", Dwarf = "Dwarf / Gnome",
    NightElf = "Night Elf", Skyborne = "Skyborne",
}
local PATH_DESC = {
    Orc = "Valley of Trials, Durotar, Orgrimmar",
    Tauren = "Red Cloud Mesa, Mulgore, Thunder Bluff",
    Undead = "Deathknell, Tirisfal Glades, Silverpine",
    Human = "Northshire, Elwynn Forest, Westfall",
    Dwarf = "Coldridge Valley, Dun Morogh, Loch Modan",
    NightElf = "Shadowglen, Teldrassil, Darkshore",
    Skyborne = "Zephras Isle",
}

function S:Build()
    local E, P = SL.Engine, SL.Player
    local f = CreateFrame("Frame", "SpeedLevelSetupFrame", UIParent)
    f:SetFrameStrata("DIALOG")
    f:SetToplevel(true)
    f:SetClampedToScreen(true)
    f:SetMovable(true)
    f:EnableMouse(true)
    f:RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", f.StartMoving)
    f:SetScript("OnDragStop", f.StopMovingOrSizing)
    f:SetPoint("CENTER", 0, 40)

    -- skin: dark panel, 1px border, gold accent along the top, soft shadow
    f.shadow = flat(f, "BACKGROUND", 0, 0, 0, 0.45)
    f.shadow:SetPoint("TOPLEFT", -6, 6)
    f.shadow:SetPoint("BOTTOMRIGHT", 6, -6)
    f.bg = flat(f, "BACKGROUND", 0.05, 0.05, 0.07, 0.97)
    f.bg:SetAllPoints()
    border(f, 1, 1, 1, 0.12)
    f.accent = flat(f, "ARTWORK", GOLD[1], GOLD[2], GOLD[3], 0.95)
    f.accent:SetHeight(3)
    f.accent:SetPoint("TOPLEFT")
    f.accent:SetPoint("TOPRIGHT")
    -- header band
    f.head = flat(f, "BACKGROUND", 1, 1, 1, 0.035)
    f.head:SetPoint("TOPLEFT", 0, -3)
    f.head:SetPoint("TOPRIGHT", 0, -3)
    f.head:SetHeight(86)

    f.logo = f:CreateTexture(nil, "ARTWORK")
    f.logo:SetSize(60, 60)
    f.logo:SetPoint("TOPLEFT", PAD - 2, -16)
    f.logo:SetTexture("Interface\\AddOns\\SpeedLevel\\Media\\Logo")
    f.brand = f:CreateFontString(nil, "OVERLAY", "GameFontNormalHuge")
    f.brand:SetPoint("TOPLEFT", f.logo, "TOPRIGHT", 12, -6)
    f.brand:SetText("MacQuest")
    f.brand:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    f.ver = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    f.ver:SetPoint("BOTTOMLEFT", f.brand, "BOTTOMRIGHT", 6, 2)
    f.ver:SetText(SL.version and ("v" .. SL.version) or "")
    f.sub = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    f.sub:SetPoint("TOPLEFT", f.brand, "BOTTOMLEFT", 0, -6)
    f.sub:SetText("Let's set up your leveling route.")
    -- the character this is for, in class colour
    local cr, cg, cb = classColor()
    local race = RACE_LABEL[P.raceName] or P.raceName or ""
    local cls = (UnitClass and select(1, UnitClass("player"))) or P.classFile or ""
    f.who = f:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    f.who:SetPoint("TOPLEFT", f.sub, "BOTTOMLEFT", 0, -4)
    f.who:SetText(string.format("%s, level %d %s %s (%s)",
        (UnitName and UnitName("player")) or "", P.level or 1, race, tostring(cls), P.faction or ""))
    f.who:SetTextColor(cr, cg, cb)

    f.close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    f.close:SetPoint("TOPRIGHT", 2, 0)
    f.close:SetScript("OnClick", function() S:Finish(false) end)

    -- the choices, prefilled with the current settings
    self.style = E:Style()
    self.dungeons = E:Dungeons()
    self.path = SL.char.startPath or "auto"

    local y = -106
    sectionLabel(f, "Route style", y)
    y = y - 18
    local rowH
    rowH = choiceRow(f, y, 76, {
        { key = "thorough", icon = "Interface\\Icons\\Ability_Rogue_Sprint", title = "Thorough", tag = "Recommended",
          desc = "Every worthwhile quest - the fastest way to 60." },
        { key = "safe", icon = "Interface\\Icons\\INV_Shield_06", title = "Safe",
          desc = "Never an orange fight: mobs at most a level above you." },
    }, self.style, function(k) S.style = k end)
    y = y - rowH - 18

    sectionLabel(f, "Dungeons", y)
    y = y - 18
    rowH = choiceRow(f, y, 76, {
        { key = false, icon = "Interface\\Icons\\INV_Sword_04", title = "Solo",
          desc = "Out in the world only. No group needed." },
        { key = true, icon = "Interface\\Icons\\INV_Misc_Key_03", title = "Include dungeons",
          desc = "Quests picked up first; the arrow leads to each entrance." },
    }, self.dungeons, function(k) S.dungeons = k end)
    y = y - rowH - 18

    -- on top of either route: Skinning on the way and a gold tracker for the level 40 mount
    self.gold = SL.char.goldMode and true or false
    sectionLabel(f, "Mount gold", y)
    y = y - 18
    rowH = choiceRow(f, y, 76, {
        { key = false, icon = "Interface\\Icons\\INV_Misc_Coin_02", title = "Just level",
          desc = "No profession stops." },
        { key = true, icon = "Interface\\Icons\\Ability_Mount_RidingHorse", title = "Mount gold mode",
          desc = "Skinning on the way and a tracker for your mount gold at 40." },
    }, self.gold, function(k) S.gold = k end)
    y = y - rowH - 18

    -- starting zones: only worth asking while you are still in them
    local choices = E:PathChoices()
    if (P.level or 1) <= 12 and #choices > 1 then
        sectionLabel(f, "Starting zones", y)
        y = y - 18
        local own = E.PATHS and (({ Troll = "Orc", Gnome = "Dwarf" })[P.raceName] or P.raceName)
        local items = {}
        for _, p in ipairs(choices) do
            items[#items + 1] = { key = (p == own) and "auto" or p, title = PATH_SHORT[p] or p,
                desc = PATH_DESC[p], tag = (p == own) and "Your race" or nil }
        end
        local h = #items >= 4 and 92 or 78
        h = choiceRow(f, y, h, items, (self.path == own) and "auto" or self.path,
            function(k) S.path = k end)
        y = y - h - 8
        local note = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
        note:SetPoint("TOPLEFT", PAD, y)
        note:SetPoint("RIGHT", -PAD, 0)
        note:SetJustifyH("LEFT")
        note:SetText("Another race's start means travelling there yourself; quests only that race can take are skipped.")
        y = y - 26
    end

    -- duo: playing together with a friend
    self.duo = SL.char.duo and true or false
    local duo = CreateFrame("CheckButton", nil, f, "UICheckButtonTemplate")
    duo:SetPoint("TOPLEFT", PAD - 4, y + 2)
    duo:SetChecked(self.duo)
    duo:SetScript("OnClick", function(b) S.duo = b:GetChecked() and true or false end)
    local dl = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    dl:SetPoint("LEFT", duo, "RIGHT", 2, 0)
    dl:SetText("Duo mode: levelling with a friend")
    local dn = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    dn:SetPoint("TOPLEFT", PAD + 26, y - 22)
    dn:SetWidth(WIDTH - 2 * PAD - 26)    -- a set width, so its height is known right away
    dn:SetJustifyH("LEFT")
    dn:SetText("Both of you: Mac Quest with duo mode on, and the same route style, dungeons and starting zone. You see each other's step and route quests are shared.")
    y = y - 22 - math.max(12, dn:GetStringHeight() or 12) - 8

    -- footer: hint + start button
    y = y - 4
    local foot = flat(f, "BACKGROUND", 1, 1, 1, 0.035)
    foot:SetPoint("TOPLEFT", 0, y)
    foot:SetPoint("TOPRIGHT", 0, y)
    foot:SetHeight(56)
    local hint = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    hint:SetPoint("TOPLEFT", PAD, y - 14)
    hint:SetWidth(WIDTH - 2 * PAD - 170)
    hint:SetJustifyH("LEFT")
    hint:SetText("Change any of this later in settings,\nor reopen this window with /sl setup.")
    local go = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    go:SetSize(160, 30)
    go:SetPoint("TOPRIGHT", -PAD, y - 13)
    go:SetText("Start leveling")
    go:SetScript("OnClick", function() S:Finish(true) end)
    f.go = go
    f:SetSize(WIDTH, -y + 56)

    -- Esc closes it like any dialog (keeping the current settings)
    if UISpecialFrames then table.insert(UISpecialFrames, "SpeedLevelSetupFrame") end
    f:SetScript("OnHide", function() if not S.finishing then S:Finish(false) end end)
    self.frame = f
    return f
end

function S:Show()
    if self.frame then self.frame:Hide(); self.frame = nil end
    local f = self:Build()
    f:SetAlpha(0)
    f:Show()
    if UIFrameFadeIn then UIFrameFadeIn(f, 0.25, 0, 1) else f:SetAlpha(1) end
end

-- apply = true: use the choices; false: keep what the character already had
function S:Finish(apply)
    local E = SL.Engine
    SL.char.dungeonsAsked = true
    SL.char.setupDone = true
    if apply then
        local mode = self.style .. (self.dungeons and "_dungeons" or "")
        if not (SL.Routes and SL.Routes[E:RouteKey(mode)]) then mode = "thorough" end
        local path = self.path ~= "auto" and self.path or nil
        local changed = mode ~= E:Mode() or path ~= SL.char.startPath or not SL.char.mode
        SL.char.mode = mode
        SL.char.startPath = path
        if (self.duo and true or false) ~= (SL.char.duo and true or false) and SL.Duo then
            SL.Duo:SetEnabled(self.duo)
        end
        if (self.gold and true or false) ~= (SL.char.goldMode and true or false) then
            SL.char.goldMode = self.gold and true or false
            E:Invalidate()
        end
        if changed then
            SL.char.routeVersion = nil
            E:LoadRoute()
            E:Resync()
        end
        SL:Print("route: |cffffd100" .. E.MODE_NAMES[mode] .. "|r" .. (SL.char.goldMode and " + mount gold mode" or "") ..
            ", start: |cffffd100" .. E:PathName() .. "|r. Good luck - /sl for help.")
    end
    if self.frame then
        self.finishing = true
        self.frame:Hide()
        self.finishing = false
        self.frame = nil
    end
end
