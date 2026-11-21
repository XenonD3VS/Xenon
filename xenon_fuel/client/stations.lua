--[[
    xenon_fuel – klient: zóny benzinek, blipy, přístupová práva
]]

StationsClient = {
    current = nil,      -- id benzinky, ve které se hráč nachází
    access = {},        -- [stationId] = přístupová data ze serveru
    blips = {},
}

local PREFIX = 'xenon_fuel:'

function StationsClient.GetPublic(stationId)
    return GlobalState[PREFIX .. stationId]
end

function StationsClient.GetLabel(stationId)
    local public = StationsClient.GetPublic(stationId)
    return public and public.label or (Utils.Stations[stationId] and Utils.Stations[stationId].label) or stationId
end

function StationsClient.IsOpen(stationId)
    local public = StationsClient.GetPublic(stationId)
    return not public or public.open ~= false
end

---------------------------------------------------------------------------------------------------
-- Blipy
---------------------------------------------------------------------------------------------------
function StationsClient.UpdateBlip(stationId)
    if not Config.Features.Blips then return end
    local station = Utils.Stations[stationId]
    if not station or not station.blip then return end

    local blip = StationsClient.blips[stationId]
    if not blip or not DoesBlipExist(blip) then
        blip = AddBlipForCoord(station.coords.x, station.coords.y, station.coords.z)
        SetBlipSprite(blip, Config.Blips.Sprite)
        SetBlipScale(blip, Config.Blips.Scale)
        SetBlipAsShortRange(blip, Config.Blips.ShortRange)
        SetBlipDisplay(blip, 4)
        StationsClient.blips[stationId] = blip
    end

    local public = StationsClient.GetPublic(stationId)
    local access = StationsClient.access[stationId]
    local colors = Config.Blips.Colors
    local color = colors.public
    if public and public.open == false then
        color = colors.closed
    elseif access and (access.isOwner or access.isEmployee) then
        color = colors.mine
    elseif public and public.owned then
        color = colors.owned
    end
    SetBlipColour(blip, color)

    BeginTextCommandSetBlipName('STRING')
    AddTextComponentSubstringPlayerName(StationsClient.GetLabel(stationId))
    EndTextCommandSetBlipName(blip)
end

local function createAllBlips()
    for _, id in ipairs(Utils.StationIds) do
        StationsClient.UpdateBlip(id)
    end
end

local function removeAllBlips()
    for id, blip in pairs(StationsClient.blips) do
        if DoesBlipExist(blip) then RemoveBlip(blip) end
        StationsClient.blips[id] = nil
    end
end

-- Změna veřejných údajů benzinky (název, otevřeno, vlastník)
AddStateBagChangeHandler(nil, 'global', function(_, key)
    if type(key) ~= 'string' or key:sub(1, #PREFIX) ~= PREFIX then return end
    local stationId = key:sub(#PREFIX + 1)
    if not Utils.Stations[stationId] then return end
    SetTimeout(0, function()
        StationsClient.UpdateBlip(stationId)
        if StationsClient.current == stationId then StationsClient.RefreshAccess(stationId) end
    end)
end)

---------------------------------------------------------------------------------------------------
-- Přístup
---------------------------------------------------------------------------------------------------
function StationsClient.RefreshAccess(stationId)
    local result = lib.callback.await('xenon_fuel:server:getAccess', false, stationId)
    if type(result) == 'table' and result.stationId then
        StationsClient.access[stationId] = result
        StationsClient.UpdateBlip(stationId)
    end
end

function StationsClient.GetAccess(stationId)
    return StationsClient.access[stationId]
end

RegisterNetEvent('xenon_fuel:client:accessUpdate', function(stationId, data)
    if not Utils.Stations[stationId] then return end
    StationsClient.access[stationId] = data
    StationsClient.UpdateBlip(stationId)
end)

local function loadAllAccess()
    local result = lib.callback.await('xenon_fuel:server:getAllAccess', false)
    if type(result) == 'table' and result.ok == nil then
        StationsClient.access = {}
        for id, data in pairs(result) do
            if Utils.Stations[id] then StationsClient.access[id] = data end
        end
    end
    createAllBlips()
end

---------------------------------------------------------------------------------------------------
-- Zóny (ox_lib points – jedna sdílená optimalizovaná smyčka)
---------------------------------------------------------------------------------------------------
for _, id in ipairs(Utils.StationIds) do
    local station = Utils.Stations[id]
    lib.points.new({
        coords = station.coords,
        distance = station.radius + 15.0,
        stationId = id,
        onEnter = function(self)
            StationsClient.current = self.stationId
            CreateThread(function() StationsClient.RefreshAccess(self.stationId) end)
        end,
        onExit = function(self)
            if StationsClient.current == self.stationId then StationsClient.current = nil end
            if Refueling then Refueling.OnLeaveStation(self.stationId) end
        end,
    })
end

---------------------------------------------------------------------------------------------------
-- Inicializace
---------------------------------------------------------------------------------------------------
Bridge.OnPlayerLoaded(function()
    Wait(1000)
    loadAllAccess()
end)

Bridge.OnPlayerLogout(function()
    StationsClient.access = {}
    createAllBlips()
end)

CreateThread(function()
    while not Bridge.IsLoaded() do Wait(500) end
    Wait(1500)
    loadAllAccess()
end)

AddEventHandler('onResourceStop', function(resource)
    if resource == GetCurrentResourceName() then removeAllBlips() end
end)
