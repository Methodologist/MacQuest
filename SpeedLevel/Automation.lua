-- SpeedLevel: automatic quest accept / turn-in (hold Shift to pause)
local _, SL = ...
local A = {}
SL.Automation = A

local function paused()
    return IsShiftKeyDown()
end

local function routeQuest(q)
    return q and SL.Engine.questSteps[q] ~= nil
end

function A:ShouldAccept(q, isTrivial)
    if not SL.ready or not SL.db.autoAccept or paused() then return false end
    if routeQuest(q) then return SL.Engine:WantQuest(q) end
    return SL.db.acceptAll and not isTrivial
end

function A:ShouldTurnIn(q)
    if not SL.ready or not SL.db.autoTurnIn or paused() then return false end
    if routeQuest(q) then return true end
    return SL.db.turnInAll
end

-- titles -> questID for the old-style greeting frame when no ID is exposed
local function idByTitle(title)
    if not title then return nil end
    for q in pairs(SL.Engine.questSteps) do
        if SL.Engine:QuestName(q) == title then return q end
    end
end

-- ------------------------------------------------------------------ gossip (modern NPC dialog)

SL:On("GOSSIP_SHOW", function()
    if not C_GossipInfo then return end
    -- turn-ins first: they give XP and can unlock what the NPC offers next
    local active = C_GossipInfo.GetActiveQuests and C_GossipInfo.GetActiveQuests() or {}
    for _, info in ipairs(active) do
        if info.isComplete and A:ShouldTurnIn(info.questID) then
            C_GossipInfo.SelectActiveQuest(info.questID)
            return
        end
    end
    local avail = C_GossipInfo.GetAvailableQuests and C_GossipInfo.GetAvailableQuests() or {}
    for _, info in ipairs(avail) do
        if A:ShouldAccept(info.questID, info.isTrivial) then
            C_GossipInfo.SelectAvailableQuest(info.questID)
            return
        end
    end
end)

-- ------------------------------------------------------------------ quest greeting (multi-quest NPCs)

SL:On("QUEST_GREETING", function()
    for i = 1, (GetNumActiveQuests() or 0) do
        local title, isComplete = GetActiveTitle(i)
        local q = GetActiveQuestID and GetActiveQuestID(i) or idByTitle(title)
        if isComplete and A:ShouldTurnIn(q) then
            SelectActiveQuest(i)
            return
        end
    end
    for i = 1, (GetNumAvailableQuests() or 0) do
        local isTrivial, _, _, _, q = GetAvailableQuestInfo(i)
        q = q or idByTitle(GetAvailableTitle(i))
        if A:ShouldAccept(q, isTrivial) then
            SelectAvailableQuest(i)
            return
        end
    end
end)

-- ------------------------------------------------------------------ quest frame

SL:On("QUEST_DETAIL", function()
    local q = GetQuestID()
    if not A:ShouldAccept(q, false) then return end
    if QuestGetAutoAccept and QuestGetAutoAccept() then
        if AcknowledgeAutoAcceptQuest then AcknowledgeAutoAcceptQuest() end
        if CloseQuest then CloseQuest() end
    else
        AcceptQuest()
    end
end)

SL:On("QUEST_ACCEPT_CONFIRM", function()  -- escort / shared quest start
    if SL.db.autoAccept and not paused() and ConfirmAcceptQuest then ConfirmAcceptQuest() end
end)

SL:On("QUEST_PROGRESS", function()
    local q = GetQuestID()
    if IsQuestCompletable() and A:ShouldTurnIn(q) then
        CompleteQuest()
    end
end)

local function bestSellChoice(n)
    local best, bestValue = nil, -1
    for i = 1, n do
        local link = GetQuestItemLink("choice", i)
        if link then
            local info = { (C_Item and C_Item.GetItemInfo or GetItemInfo)(link) }
            local sell = info[11] or 0
            local _, _, count = GetQuestItemInfo("choice", i)
            sell = sell * (count or 1)
            if sell > bestValue then best, bestValue = i, sell end
        end
    end
    return best
end

SL:On("QUEST_COMPLETE", function()
    local q = GetQuestID()
    if not A:ShouldTurnIn(q) then return end
    local n = GetNumQuestChoices() or 0
    if n <= 1 then
        GetQuestReward(1)
    elseif SL.db.autoReward then
        local i = bestSellChoice(n)
        if i then GetQuestReward(i) end
    end
    -- otherwise leave the reward choice to the player
end)
