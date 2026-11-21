--[[
    xenon_fuel – inicializace serveru
    Autor: XenonD3VS
]]

local resourceName = GetCurrentResourceName()

local function checkDependencies()
    local required = { Config.FrameworkResource, 'ox_lib', 'oxmysql', 'ox_target' }
    if Config.Features.Receipts then required[#required + 1] = 'ox_inventory' end
    local ok = true
    for _, res in ipairs(required) do
        local state = GetResourceState(res)
        if state ~= 'started' and state ~= 'starting' then
            print(('^1[xenon_fuel] Chybí závislost: %s (stav: %s)^7'):format(res, state))
            ok = false
        end
    end
    if not Bridge then
        print(('^1[xenon_fuel] Nepodporovaný framework "%s". Podporováno: esx^7'):format(tostring(Config.Framework)))
        ok = false
    end
    return ok
end

MySQL.ready(function()
    if not checkDependencies() then
        print('^1[xenon_fuel] Script nebyl spuštěn kvůli chybějícím závislostem.^7')
        return
    end

    local ok, err = pcall(function()
        Database.Init()
        Stations.Load()
        if Config.Features.Employees then Employees.Load() end
        if Config.Features.Orders then Deliveries.Load() end
    end)

    if not ok then
        print(('^1[xenon_fuel] Inicializace selhala: %s^7'):format(tostring(err)))
        return
    end

    Fuel.StartSaveLoop()
    Employees.StartPayrollLoop()
    Deliveries.StartLoops()

    Core.Ready = true
    print(('^2[xenon_fuel]^7 v%s připraven – XenonD3VS'):format(GetResourceMetadata(resourceName, 'version', 0) or '1.0.0'))
end)

---------------------------------------------------------------------------------------------------
-- Uložení všech dat při vypnutí
---------------------------------------------------------------------------------------------------
local shuttingDown = false

local function shutdown()
    if shuttingDown or not Core.Ready then return end
    shuttingDown = true
    Refuel.FinishAll('stopped')
    Deliveries.EndAllJobs()
    Employees.SaveAll()
    Fuel.Flush(true)
    Stations.SaveAllPending(true)
end

AddEventHandler('onResourceStop', function(resource)
    if resource ~= resourceName then return end
    shutdown()
end)

AddEventHandler('txAdmin:events:serverShuttingDown', function()
    if not Core.Ready then return end
    Refuel.FinishAll('stopped')
    Employees.SaveAll()
    Fuel.Flush(false)
    Stations.SaveAllPending(false)
end)

AddEventHandler('txAdmin:events:scheduledRestart', function(data)
    if Core.Ready and data and data.secondsRemaining and data.secondsRemaining <= 60 then
        Fuel.Flush(false)
    end
end)
