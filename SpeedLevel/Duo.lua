-- MacQuest: duo mode - levelling together.
-- Party members who run the guide with duo mode on trade a small status over addon messages:
-- their route, their current step and its progress, and the quests in their log (finished or not).
-- The guide window shows your partner's step under your own (click it to join them), offers a route
-- quest you accept to a partner who needs it too (their auto-accept takes it), and on a turn-in
-- says when your partner still needs that quest.
local _, SL = ...
local D = {}
SL.Duo = D

local PREFIX = "MacQuest"
local SEP = "~"
local STALE = 120      -- seconds without news before a partner drops off the window
local HEARTBEAT = 30   -- resend the status at least this often
D.PREFIX = PREFIX
D.peers = {}           -- [name] = { name, sig, level, cursor, q, prog, zone, log = { [q] = finished }, t }

local function now() return GetTime and GetTime() or 0 end
local function me() return UnitName and UnitName("player") or "" end

function D:Enabled() return SL.char and SL.char.duo and true or false end

-- a party (not a raid): duo mode talks to the other members of it
function D:Grouped()
    if IsInRaid and SL.Clean(IsInRaid()) then return false end
    return IsInGroup and SL.Clean(IsInGroup()) and true or false
end

function D:Send(msg)
    if #msg > 250 then msg = msg:sub(1, 250) end
    if C_ChatInfo and C_ChatInfo.SendAddonMessage then
        C_ChatInfo.SendAddonMessage(PREFIX, msg, "PARTY")
    elseif SendAddonMessage then
        SendAddonMessage(PREFIX, msg, "PARTY")
    end
end

local function split(s)
    local out = {}
    for part in (s .. SEP):gmatch("(.-)" .. SEP) do out[#out + 1] = part end
    return out
end

-- same addon version and same route file: step numbers mean the same step on both sides
function D:Signature()
    return (SL.version or "dev") .. "/" .. SL.Engine:RouteKey()
end

local function progress(q)
    local P = SL.Player
    if not q or not P:InLog(q) then return "" end
    if P:IsQuestReady(q) then return "done" end
    local have, need = 0, 0
    for _, o in ipairs(P:Objectives(q) or {}) do
        if (o.numRequired or 0) > 0 then
            have = have + math.min(o.numFulfilled or 0, o.numRequired)
            need = need + o.numRequired
        end
    end
    return need > 0 and (have .. "/" .. need) or ""
end

function D:StatusMsg()
    local E = SL.Engine
    local st, i = E:Current()
    local sec = st and E.sections[st.sec]
    local q = st and st.q
    return table.concat({ "S", self:Signature(), SL.Player.level or 1, i or 0, q or 0, progress(q),
        ((sec and sec.title) or ""):sub(1, 40) }, SEP)
end

function D:LogMsg()
    local ids = {}
    for q in pairs(SL.Player.log or {}) do
        if type(q) == "number" then ids[#ids + 1] = q end
    end
    table.sort(ids)
    local parts = {}
    for _, q in ipairs(ids) do parts[#parts + 1] = q .. (SL.Player:IsQuestReady(q) and "*" or "") end
    return "L" .. SEP .. table.concat(parts, ",")
end

-- send what changed (at most once a second), and everything every HEARTBEAT seconds
function D:Push(force)
    if not (self:Enabled() and self:Grouped() and SL.ready) then return end
    local t = now()
    local s, l = self:StatusMsg(), self:LogMsg()
    local due = force or t - (self.lastT or -1e9) >= HEARTBEAT
    if not due and s == self.lastS and l == self.lastL then return end
    if not force and t - (self.lastT or -1e9) < 1 then
        if not self.pending then
            self.pending = true
            C_Timer.After(1.1, function() self.pending = false; self:Push() end)
        end
        return
    end
    if due or s ~= self.lastS then self:Send(s) end
    if due or l ~= self.lastL then self:Send(l) end
    self.lastS, self.lastL, self.lastT = s, l, t
end

-- would I take this quest if my partner shared it?
function D:Wants(q)
    local E, P = SL.Engine, SL.Player
    if not q or P:InLog(q) or P:IsCompleted(q) then return false end
    local qs = E.questSteps[q]
    if not (qs and qs.A) then return false end
    local st = E.steps[qs.A]
    if st and st.grp then return true end                  -- an elite quest: that's what the duo is for
    return E:WantQuest(q)
end

function D:Share(q)
    if not (GetQuestLogIndexByID and SelectQuestLogEntry and QuestLogPushQuest) then return end
    local idx = GetQuestLogIndexByID(q)
    if not idx or idx == 0 then return end
    SelectQuestLogEntry(idx)
    if GetQuestLogPushable and not GetQuestLogPushable() then return end
    QuestLogPushQuest()
end

function D:OnMessage(prefix, msg, channel, sender)
    if prefix ~= PREFIX or type(msg) ~= "string" or not sender then return end
    local name = Ambiguate and Ambiguate(sender, "none") or sender:gsub("%-.*$", "")
    if name == me() then return end
    if not self:Enabled() then
        -- a party member levels in duo mode and you don't: say how to join in (once per session)
        self.told = self.told or {}
        if msg:sub(1, 2) == "S" .. SEP and not self.told[name] then
            self.told[name] = true
            SL:Print(string.format("|cff66ccff%s|r is levelling in duo mode - type |cffffd100/mq duo on|r to see each other's step and share quests.", name))
        end
        return
    end
    local f = split(msg)
    local kind = f[1]
    local p = self.peers[name]
    if not p then
        p = { name = name, log = {} }
        self.peers[name] = p
    end
    p.t = now()
    if kind == "S" then
        local first = not p.sig
        p.sig, p.level, p.cursor, p.q = f[2], tonumber(f[3]), tonumber(f[4]), tonumber(f[5])
        p.prog, p.zone = f[6] or "", f[7] or ""
        if p.q == 0 then p.q = nil end
        if first then
            SL:Print(string.format("duo: |cff66ccff%s|r is here with Mac Quest.", name))
            self:Push(true)                                  -- so they know about us too
        end
    elseif kind == "L" then
        p.log = {}
        for e in (f[2] or ""):gmatch("[^,]+") do
            local q, star = e:match("^(%d+)(%*?)$")
            if q then p.log[tonumber(q)] = (star == "*") end
        end
        p.hasLog = true
    elseif kind == "H" then
        self:Push(true)
    elseif kind == "Q" then                                  -- they took a route quest: do I want it?
        local q = tonumber(f[2])
        if q and self:Wants(q) then self:Send("W" .. SEP .. q .. SEP .. name) end
    elseif kind == "W" then                                  -- yes please (addressed to one sharer)
        local q = tonumber(f[2])
        if q and f[3] == me() then
            p.shared = p.shared or {}
            if not p.shared[q] then
                p.shared[q] = true
                self:Share(q)
            end
        end
    end
    SL:RequestUpdate()
end

function D:OnAccepted(a, b)
    if not (self:Enabled() and self:Grouped()) or SL.db.duoShare == false then return end
    local q = b
    if not q and a and GetQuestLogTitle then q = select(8, GetQuestLogTitle(a)) end
    if type(q) ~= "number" or not SL.Engine.questSteps[q] then return end
    local anyone = false
    for _, p in pairs(self.peers) do
        if now() - (p.t or 0) <= STALE and not (p.hasLog and p.log[q] ~= nil) then anyone = true end
    end
    if anyone then self:Send("Q" .. SEP .. q) end
end

function D:OnRoster()
    if not self:Enabled() then return end
    if not self:Grouped() then
        self.peers = {}
        return
    end
    if UnitInParty then
        for name in pairs(self.peers) do
            if not SL.Clean(UnitInParty(name)) then self.peers[name] = nil end
        end
    end
    self:Send("H")
    self:Push(true)
end

function D:Peers()
    local out = {}
    if not (self:Enabled() and self:Grouped()) then return out end
    local t = now()
    for _, p in pairs(self.peers) do
        if p.sig and t - (p.t or 0) <= STALE then out[#out + 1] = p end
    end
    table.sort(out, function(x, y) return x.name < y.name end)
    return out
end

-- joining a partner's step: their objective or turn-in needs the quest, so without it the pickup
-- comes first (unless you already finished that quest: then their step is not yours to do)
function D:JoinTarget(idx)
    local E, P = SL.Engine, SL.Player
    local st = E.steps[idx]
    if st and st.q and st.t ~= "A" and not P:InLog(st.q) then
        local qs = E.questSteps[st.q]
        if P:IsCompleted(st.q) or not (qs and qs.A) then return nil end
        return qs.A
    end
    return idx
end

-- lines for the guide window: { text =, join = step index to jump to (same route only), name = }
function D:Lines()
    local out = {}
    local E, P = SL.Engine, SL.Player
    local cur, i = E:Current()
    local group = E:CurrentGroup()
    for _, p in ipairs(self:Peers()) do
        local who = string.format("|cff66ccff%s|r |cff888888%d|r", p.name, p.level or 0)
        local ver, key = (p.sig or ""):match("^(.-)/(.*)$")
        if p.sig == self:Signature() then
            local st = p.cursor and E.steps[p.cursor]
            if st then
                local _, text = E:StepText(st)
                local prog = (p.prog ~= "" and p.prog ~= "done") and (" |cffdddddd" .. p.prog .. "|r") or
                    (p.prog == "done" and " |cff40ff40(done)|r" or "")
                local rel, join = "", nil
                if p.cursor == i then
                    rel = "|cff40ff40same step|r - "
                elseif p.cursor < (i or 0) then
                    rel, join = "|cffffd040behind|r - ", self:JoinTarget(p.cursor)
                else
                    rel, join = "|cffffd040ahead|r - ", self:JoinTarget(p.cursor)
                end
                out[#out + 1] = { name = p.name, join = join, text = who .. "  " .. rel .. text .. prog }
            end
        elseif ver ~= (SL.version or "dev") then
            out[#out + 1] = { name = p.name, text = who .. string.format(
                "  |cffff9933uses Mac Quest %s (you: %s) - update both to stay in step|r", ver or "?", SL.version or "dev") }
        else
            local mode = key and key:match("^%a+_(.+)$")
            out[#out + 1] = { name = p.name, text = who .. string.format(
                "  |cffff9933is on %s (you: %s) - pick the same route style and dungeons to stay in step|r",
                (mode and E.MODE_NAMES[mode]) or tostring(key), E.MODE_NAMES[E:Mode()] or E:Mode()) }
        end
        -- about to turn in a quest your partner is still working on
        if p.hasLog then
            for _, idx in ipairs(group) do
                local st = E.steps[idx]
                if st.t == "T" and st.q and p.log[st.q] == false and P:IsQuestReady(st.q) then
                    out[#out + 1] = { name = p.name, text = string.format(
                        "    |cff999999%s still needs %s - help them finish first?|r", p.name, E:QuestName(st.q)) }
                    break
                end
            end
        end
    end
    return out
end

function D:SetEnabled(on)
    SL.char.duo = on and true or false
    self.peers = {}
    self.lastS, self.lastL, self.lastT = nil, nil, nil
    if on then
        SL:Print("duo mode |cff40ff40on|r: group up with your partner (both with Mac Quest and duo mode on). Pick the same route style, dungeons and starting zone to stay in step.")
        if self:Grouped() then self:Send("H"); self:Push(true) end
    else
        SL:Print("duo mode |cffff6060off|r.")
    end
    SL:RequestUpdate()
end

function D:Init()
    if C_ChatInfo and C_ChatInfo.RegisterAddonMessagePrefix then
        C_ChatInfo.RegisterAddonMessagePrefix(PREFIX)
    elseif RegisterAddonMessagePrefix then
        RegisterAddonMessagePrefix(PREFIX)
    end
    SL:On("CHAT_MSG_ADDON", function(_, prefix, msg, channel, sender) D:OnMessage(prefix, msg, channel, sender) end)
    SL:On("GROUP_ROSTER_UPDATE", function() D:OnRoster() end)
    SL:On("QUEST_ACCEPTED", function(_, a, b) D:OnAccepted(a, b) end)
    if C_Timer and C_Timer.NewTicker then C_Timer.NewTicker(15, function() D:Push() end) end
    if self:Enabled() and self:Grouped() then C_Timer.After(3, function() D:Send("H"); D:Push(true) end) end
end
