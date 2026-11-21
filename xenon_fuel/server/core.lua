--[[
    xenon_fuel – serverové jádro (pomocné funkce sdílené všemi moduly)
    Autor: XenonD3VS
]]

Core = {
    Ready = false,
}

local cooldowns = {}
local locks = {}

--- Omezení frekvence akcí hráče (ochrana proti spamu a duplicitním požadavkům)
---@return boolean povoleno
function Core.Throttle(source, key, ms)
    local now = GetGameTimer()
    local list = cooldowns[source]
    if not list then
        list = {}
        cooldowns[source] = list
    end
    local last = list[key]
    if last and now - last < (ms or Config.Security.ActionCooldown) then
        return false
    end
    list[key] = now
    return true
end

--- Jednoduchý zámek pro operace, které nesmí běžet souběžně (např. platby jednoho hráče)
function Core.Lock(key)
    if locks[key] then return false end
    locks[key] = true
    return true
end

function Core.Unlock(key)
    locks[key] = nil
end

function Core.Suspicious(source, reason)
    if not Config.Security.LogSuspicious then return end
    print(('^1[xenon_fuel] Podezřelý požadavek^7 – hráč %s (%s): %s'):format(
        tostring(source), GetPlayerName(source) or '?', reason
    ))
end

function Core.Notify(source, message, notifyType)
    TriggerClientEvent('xenon_fuel:client:notify', source, message, notifyType or 'info')
end

function Core.GetPlayerCoords(source)
    local ped = GetPlayerPed(source)
    if not ped or ped == 0 then return nil end
    return GetEntityCoords(ped)
end

--- Vzdálenost hráče od bodu (nil pokud hráč neexistuje)
function Core.PlayerDistance(source, coords)
    local pos = Core.GetPlayerCoords(source)
    if not pos then return nil end
    return #(pos - coords)
end

function Core.Fail(errorKey, ...)
    return { ok = false, error = errorKey, message = L(errorKey, ...) }
end

function Core.Success(data, messageKey, ...)
    local result = { ok = true, data = data }
    if messageKey then result.message = L(messageKey, ...) end
    return result
end

--- Registrace callbacku s jednotnou ochranou (připravenost, načtený hráč, ošetření chyb)
function Core.RegisterCallback(name, handler)
    lib.callback.register('xenon_fuel:server:' .. name, function(source, ...)
        if not Core.Ready then return Core.Fail('error_not_ready') end
        if not Bridge.GetPlayer(source) then return Core.Fail('error_no_player') end
        local ok, result = pcall(handler, source, ...)
        if not ok then
            print(('^1[xenon_fuel] Chyba v callbacku %s: %s^7'):format(name, tostring(result)))
            return Core.Fail('error_internal')
        end
        return result
    end)
end

--- Registrace síťového eventu s ochranou
function Core.RegisterNetEvent(name, handler)
    RegisterNetEvent('xenon_fuel:server:' .. name, function(...)
        local source = source
        if not Core.Ready or not Bridge.GetPlayer(source) then return end
        local ok, err = pcall(handler, source, ...)
        if not ok then
            print(('^1[xenon_fuel] Chyba v eventu %s: %s^7'):format(name, tostring(err)))
        end
    end)
end

AddEventHandler('playerDropped', function()
    cooldowns[source] = nil
end)
