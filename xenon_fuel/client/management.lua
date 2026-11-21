--[[
    xenon_fuel – klient: management panel, nákup benzinky, nabídky práce
]]

Management = {
    stationId = nil,
    purchaseId = nil,
}

---------------------------------------------------------------------------------------------------
-- Management panel
---------------------------------------------------------------------------------------------------
function Management.Open(stationId)
    if not stationId or Management.stationId then return end
    local result = Client.Call('openManagement', stationId)
    if not result.ok then
        return Notify(result.message, 'error')
    end
    Management.stationId = stationId
    Nui.Open('management', result.data)
end

Nui.onClose.management = function()
    Management.stationId = nil
end

local silentActions = { salesPage = true, financePage = true, nearbyPlayers = true, refresh = true }

RegisterNUICallback('mgmt:action', function(data, cb)
    local stationId = Management.stationId
    if not stationId or type(data) ~= 'table' or type(data.action) ~= 'string' then
        return cb({ ok = false, message = L('error_invalid_data') })
    end

    local result = Client.Call('mgmtAction', stationId, data.action, data.payload or {})
    cb(result)

    if result.message and (not silentActions[data.action] or not result.ok) then
        Notify(result.message, result.ok and 'success' or 'error')
    end
    if result.closed then
        Nui.Close('management')
    end
    StationsClient.RefreshAccess(stationId)
end)

--- Přihlášení / odhlášení ze směny přímo z ox_target
function Management.ToggleDuty(stationId)
    local result = Client.Call('mgmtAction', stationId, 'duty', {})
    Notify(result.message, result.ok and 'success' or 'error')
    StationsClient.RefreshAccess(stationId)
end

---------------------------------------------------------------------------------------------------
-- Nákup benzinky
---------------------------------------------------------------------------------------------------
function Management.OpenPurchase(stationId)
    if not stationId then return end
    local result = Client.Call('getPurchaseInfo', stationId)
    if not result.ok then
        return Notify(result.message, 'error')
    end
    Management.purchaseId = stationId
    Nui.Open('purchase', result.data)
end

Nui.onClose.purchase = function()
    Management.purchaseId = nil
end

RegisterNUICallback('purchase:confirm', function(data, cb)
    local stationId = Management.purchaseId
    if not stationId or type(data) ~= 'table' then
        return cb({ ok = false, message = L('error_invalid_data') })
    end
    local result = Client.Call('buyStation', stationId, data.method)
    cb(result)
    Notify(result.message, result.ok and 'success' or 'error')
    if result.ok then
        Nui.Close('purchase')
        StationsClient.RefreshAccess(stationId)
    end
end)

---------------------------------------------------------------------------------------------------
-- Nabídka práce
---------------------------------------------------------------------------------------------------
local offerToken = 0

RegisterNetEvent('xenon_fuel:client:jobOffer', function(offer)
    if type(offer) ~= 'table' then return end
    offerToken = offerToken + 1
    local token = offerToken
    Nui.Open('offer', offer)
    SetTimeout((offer.timeout or 45) * 1000, function()
        if token == offerToken and Nui.IsOpen('offer') then
            Nui.Close('offer')
            TriggerServerEvent('xenon_fuel:server:respondOffer', false)
        end
    end)
end)

RegisterNUICallback('offer:respond', function(data, cb)
    cb(1)
    if not Nui.IsOpen('offer') then return end
    offerToken = offerToken + 1
    Nui.Close('offer')
    TriggerServerEvent('xenon_fuel:server:respondOffer', type(data) == 'table' and data.accepted == true)
end)
