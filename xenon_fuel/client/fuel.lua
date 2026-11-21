--[[
    xenon_fuel – klient: spotřeba paliva, HUD, upozornění, blokace motoru

    Smyčka běží pouze ve chvíli, kdy hráč sedí na místě řidiče. Mimo vozidlo je resmon 0.00 ms.
]]

FuelClient = {}

local cfg = Config.Consumption
local thresholds = {}
for _, t in ipairs(Config.Warnings.Thresholds) do thresholds[#thresholds + 1] = t end
table.sort(thresholds, function(a, b) return a > b end)

local activeVehicle = nil
local hudVisible = false
local lastHud = nil

local function hideHud()
    if hudVisible then
        hudVisible = false
        lastHud = nil
        Nui.Send('hud', { show = false })
    end
end

local function updateHud(fuel, profile, engineOn)
    if not Config.Features.Hud then return end
    if not engineOn and not Config.Hud.ShowWhenEngineOff then
        return hideHud()
    end
    local rounded = Utils.Round(fuel, 1)
    if hudVisible and lastHud == rounded then return end
    hudVisible = true
    lastHud = rounded
    Nui.Send('hud', {
        show = true,
        fuel = rounded,
        low = fuel <= Config.Hud.LowThreshold,
        amount = Utils.Round(profile.capacity * fuel / 100, 1),
        unit = profile.category == 'electric' and 'kwh' or 'l',
        electric = profile.category == 'electric',
    })
end

local function canSetState(vehicle)
    return NetworkGetEntityOwner(vehicle) == cache.playerId
end

--- Zablokuje / odblokuje vozidlo bez paliva
local function setEngineLock(vehicle, locked)
    if not Config.Features.EngineLock then return end
    local state = Entity(vehicle).state
    if locked then
        SetVehicleEngineOn(vehicle, false, true, true)
        SetVehicleUndriveable(vehicle, true)
        if not state.fuelLocked and canSetState(vehicle) then state:set('fuelLocked', true, true) end
    elseif state.fuelLocked then
        SetVehicleUndriveable(vehicle, false)
        SetVehicleEngineOn(vehicle, false, true, false)
        if canSetState(vehicle) then state:set('fuelLocked', false, true) end
    end
end

local function warn(level)
    Notify(L('warning_low_fuel', level), level <= 10 and 'error' or 'warning')
    if Config.Warnings.Sound then Client.PlaySound('warning') end
end

local function driveLoop(vehicle)
    if activeVehicle == vehicle then return end
    activeVehicle = vehicle

    CreateThread(function()
        local class = GetVehicleClass(vehicle)
        local profile = Utils.GetVehicleProfile(GetEntityModel(vehicle), class)
        if not profile then
            activeVehicle = nil
            return
        end

        local state = Entity(vehicle).state
        if state.fuel == nil then
            lib.callback.await('xenon_fuel:server:initVehicle', false, NetworkGetNetworkIdFromEntity(vehicle), class)
            local timeout = GetGameTimer() + 3000
            while state.fuel == nil and GetGameTimer() < timeout do Wait(100) end
        end

        local fuel = Utils.ToNumber(state.fuel) or GetVehicleFuelLevel(vehicle)
        local synced = fuel
        local warnedLevel = 101
        for _, t in ipairs(thresholds) do
            if fuel <= t then warnedLevel = t end -- při nástupu neupozorňovat na již překročené hranice
        end
        if warnedLevel <= 100 and Config.Features.LowFuelWarnings then warn(warnedLevel) end

        local interval = cfg.Interval
        local last = GetGameTimer()
        local ped = cache.ped

        while DoesEntityExist(vehicle) and GetVehiclePedIsIn(ped, false) == vehicle and GetPedInVehicleSeat(vehicle, -1) == ped do
            local now = GetGameTimer()
            local dt = (now - last) / 1000
            last = now

            -- hodnota ze serveru (tankování, admin) má přednost, pokud je vyšší
            local serverFuel = Utils.ToNumber(state.fuel)
            if serverFuel and math.abs(serverFuel - synced) > 0.01 then
                fuel = serverFuel
                synced = serverFuel
            end

            local engineOn = GetIsVehicleEngineRunning(vehicle)
            if Config.Features.Consumption and engineOn and fuel > 0 then
                local rpm = GetVehicleCurrentRpm(vehicle)
                local speed = GetEntitySpeed(vehicle) * 3.6
                local fuelType = state.fuelType and Config.FuelTypes[state.fuelType]
                local rate = (cfg.Idle + cfg.Rpm * (rpm ^ cfg.RpmExponent) + cfg.Speed * speed)
                    * profile.consumption * (fuelType and fuelType.consumption or 1.0) * cfg.GlobalMultiplier
                fuel = math.max(0.0, fuel - rate * dt)
            end

            SetVehicleFuelLevel(vehicle, fuel + 0.0)

            if fuel <= 0.0 then
                setEngineLock(vehicle, true)
            elseif state.fuelLocked then
                setEngineLock(vehicle, false)
            end

            if (synced - fuel >= cfg.SyncThreshold or (fuel == 0 and synced ~= 0)) and canSetState(vehicle) then
                synced = Utils.Round(fuel, 2)
                state:set('fuel', synced, true)
            end

            if Config.Features.LowFuelWarnings then
                for _, t in ipairs(thresholds) do
                    if fuel <= t and t < warnedLevel then
                        warnedLevel = t
                        warn(t)
                        break
                    end
                end
                if fuel > (thresholds[1] or 0) + 1 then warnedLevel = 101 end
            end

            updateHud(fuel, profile, engineOn)
            Wait(interval)
        end

        -- finální synchronizace při vystoupení
        if DoesEntityExist(vehicle) and synced - fuel >= 0.05 and canSetState(vehicle) then
            state:set('fuel', Utils.Round(fuel, 2), true)
        end
        hideHud()
        activeVehicle = nil
    end)
end

local function onSeatChange(seat)
    if seat == -1 and cache.vehicle then
        driveLoop(cache.vehicle)
    end
end

lib.onCache('seat', function(seat)
    -- cache.seat se aktualizuje až po zavolání handleru – smyčka startuje v novém vlákně
    SetTimeout(0, function() onSeatChange(seat) end)
end)

CreateThread(function()
    Wait(1000)
    if cache.vehicle and cache.seat == -1 then driveLoop(cache.vehicle) end
end)

-- Aktualizace ukazatele na palubní desce u vozidel kolem (např. po natankování)
AddStateBagChangeHandler('fuel', nil, function(bagName, _, value)
    local entity = GetEntityFromStateBagName(bagName)
    if entity == 0 or entity == activeVehicle then return end
    local fuel = Utils.ToNumber(value)
    if fuel then SetVehicleFuelLevel(entity, fuel + 0.0) end
end)

---------------------------------------------------------------------------------------------------
-- Exporty
---------------------------------------------------------------------------------------------------
function FuelClient.Get(vehicle)
    if not vehicle or not DoesEntityExist(vehicle) then return 0 end
    return Utils.ToNumber(Entity(vehicle).state.fuel) or GetVehicleFuelLevel(vehicle)
end

exports('GetFuel', FuelClient.Get)

--- Klient smí palivo pouze snížit. Doplnění paliva provádí server (export SetFuel na serveru).
exports('SetFuel', function(vehicle, value)
    value = Utils.ToNumber(value)
    if not vehicle or not DoesEntityExist(vehicle) or not value then return false end
    local current = FuelClient.Get(vehicle)
    if value > current then
        Utils.Debug('Klientský export SetFuel nemůže palivo zvýšit – použij server export.')
        return false
    end
    if not canSetState(vehicle) then return false end
    Entity(vehicle).state:set('fuel', Utils.Round(Utils.Clamp(value, 0, 100), 2), true)
    return true
end)

AddEventHandler('onResourceStop', function(resource)
    if resource ~= GetCurrentResourceName() then return end
    if activeVehicle and DoesEntityExist(activeVehicle) and Entity(activeVehicle).state.fuelLocked then
        SetVehicleUndriveable(activeVehicle, false)
    end
end)
