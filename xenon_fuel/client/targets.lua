--[[
    xenon_fuel – klient: ox_target interakce (stojany, vozidla, správa)
]]

local target = exports.ox_target
local registeredZones = {}

--- Benzinka, ke které patří stojan (entita modelu z Config.Refuel.PumpModels)
local function pumpStation(entity)
    local coords = GetEntityCoords(entity)
    local current = StationsClient.current and Utils.Stations[StationsClient.current]
    if current and current.pumps == 'auto' and #(coords - current.coords) <= current.radius then
        return current
    end
    return Utils.GetStationAt(coords, true)
end

local function pumpFromEntity(entity)
    local station = pumpStation(entity)
    if not station then return nil end
    return { entity = entity, coords = GetEntityCoords(entity), stationId = station.id }
end

local function access(stationId)
    return stationId and StationsClient.GetAccess(stationId) or nil
end

local function canBuy(stationId)
    if not Config.Features.Ownership then return false end
    local station = Utils.Stations[stationId]
    if not station or not station.purchasable then return false end
    local public = StationsClient.GetPublic(stationId)
    return not (public and public.owned)
end

--- Sada možností pro správu benzinky (stojany i místo pro správu)
local function managementOptions(getStationId)
    if not Config.Features.Ownership then return {} end
    return {
        {
            name = 'xenon_fuel:manage',
            icon = 'fa-solid fa-chart-line',
            label = L('target_manage'),
            distance = 2.0,
            canInteract = function(entity)
                if Refueling.IsHolding() then return false end
                local a = access(getStationId(entity))
                return a ~= nil and a.canManage == true
            end,
            onSelect = function(data)
                Management.Open(getStationId(data.entity))
            end,
        },
        {
            name = 'xenon_fuel:duty_on',
            icon = 'fa-solid fa-user-clock',
            label = L('target_duty_on'),
            distance = 2.0,
            canInteract = function(entity)
                if not Config.Features.Employees or Refueling.IsHolding() then return false end
                local a = access(getStationId(entity))
                return a ~= nil and a.isEmployee and not a.onDuty
            end,
            onSelect = function(data)
                Management.ToggleDuty(getStationId(data.entity))
            end,
        },
        {
            name = 'xenon_fuel:duty_off',
            icon = 'fa-solid fa-user-xmark',
            label = L('target_duty_off'),
            distance = 2.0,
            canInteract = function(entity)
                if not Config.Features.Employees or Refueling.IsHolding() then return false end
                local a = access(getStationId(entity))
                return a ~= nil and a.isEmployee and a.onDuty
            end,
            onSelect = function(data)
                Management.ToggleDuty(getStationId(data.entity))
            end,
        },
        {
            name = 'xenon_fuel:buy',
            icon = 'fa-solid fa-file-signature',
            label = L('target_buy'),
            distance = 2.0,
            canInteract = function(entity)
                if Refueling.IsHolding() then return false end
                return canBuy(getStationId(entity))
            end,
            onSelect = function(data)
                Management.OpenPurchase(getStationId(data.entity))
            end,
        },
    }
end

---------------------------------------------------------------------------------------------------
-- Stojany s automatickou detekcí (modely)
---------------------------------------------------------------------------------------------------
local function autoPumpStationId(entity)
    local station = entity and pumpStation(entity)
    return station and station.id or nil
end

local pumpOptions = {
    {
        name = 'xenon_fuel:take_nozzle',
        icon = 'fa-solid fa-gas-pump',
        label = L('target_take_nozzle'),
        distance = 2.0,
        canInteract = function(entity)
            return not Refueling.IsHolding() and not cache.vehicle and pumpStation(entity) ~= nil
        end,
        onSelect = function(data)
            local pump = pumpFromEntity(data.entity)
            if pump then Refueling.TakeNozzle(pump) end
        end,
    },
    {
        name = 'xenon_fuel:return_nozzle',
        icon = 'fa-solid fa-rotate-left',
        label = L('target_return_nozzle'),
        distance = 2.5,
        canInteract = function(entity)
            return Refueling.IsHoldingFrom(entity)
        end,
        onSelect = function()
            Refueling.ReturnNozzle(false)
        end,
    },
}

if Config.Ownership.TargetOnPumps then
    for _, option in ipairs(managementOptions(autoPumpStationId)) do
        pumpOptions[#pumpOptions + 1] = option
    end
end

target:addModel(Config.Refuel.PumpModels, pumpOptions)

---------------------------------------------------------------------------------------------------
-- Ručně definované stojany (sphere zóny) a místa pro správu
---------------------------------------------------------------------------------------------------
for _, stationId in ipairs(Utils.StationIds) do
    local station = Utils.Stations[stationId]
    local getId = function() return stationId end

    if type(station.pumps) == 'table' then
        for _, pump in ipairs(station.pumps) do
            local pumpData = { coords = pump.coords, index = pump.index, stationId = stationId }
            local options = {
                {
                    name = 'xenon_fuel:take_nozzle',
                    icon = 'fa-solid fa-gas-pump',
                    label = L('target_take_nozzle'),
                    distance = 2.0,
                    canInteract = function()
                        return not Refueling.IsHolding() and not cache.vehicle
                    end,
                    onSelect = function()
                        Refueling.TakeNozzle(pumpData)
                    end,
                },
                {
                    name = 'xenon_fuel:return_nozzle',
                    icon = 'fa-solid fa-rotate-left',
                    label = L('target_return_nozzle'),
                    distance = 2.5,
                    canInteract = function()
                        return Refueling.IsHoldingFrom(nil, pump.index) and Refueling.GetHolding().pump.stationId == stationId
                    end,
                    onSelect = function()
                        Refueling.ReturnNozzle(false)
                    end,
                },
            }
            if Config.Ownership.TargetOnPumps then
                for _, option in ipairs(managementOptions(getId)) do options[#options + 1] = option end
            end
            registeredZones[#registeredZones + 1] = target:addSphereZone({
                coords = pump.coords,
                radius = 1.2,
                debug = Config.Debug,
                options = options,
            })
        end
    end

    if station.management then
        local m = station.management
        registeredZones[#registeredZones + 1] = target:addSphereZone({
            coords = vector3(m.x, m.y, m.z),
            radius = 1.0,
            debug = Config.Debug,
            options = managementOptions(getId),
        })
    end
end

---------------------------------------------------------------------------------------------------
-- Vozidla
---------------------------------------------------------------------------------------------------
local vehicleOptions = {
    {
        name = 'xenon_fuel:refuel',
        icon = 'fa-solid fa-gas-pump',
        label = L('target_refuel'),
        distance = 3.0,
        canInteract = function(entity)
            return Refueling.CanRefuelVehicle(entity)
        end,
        onSelect = function(data)
            Refueling.OpenMenu(data.entity)
        end,
    },
}

if Config.Features.TankerJob and Config.Features.Orders then
    vehicleOptions[#vehicleOptions + 1] = {
        name = 'xenon_fuel:load_tanker',
        icon = 'fa-solid fa-oil-well',
        label = L('target_load_tanker'),
        distance = 4.0,
        canInteract = function(entity)
            return Deliveries.CanLoad(entity)
        end,
        onSelect = function()
            Deliveries.LoadTanker()
        end,
    }
    vehicleOptions[#vehicleOptions + 1] = {
        name = 'xenon_fuel:unload_tanker',
        icon = 'fa-solid fa-truck-droplet',
        label = L('target_unload_tanker'),
        distance = 4.0,
        canInteract = function(entity)
            return Deliveries.CanUnload(entity)
        end,
        onSelect = function()
            Deliveries.UnloadTanker()
        end,
    }
end

target:addGlobalVehicle(vehicleOptions)

---------------------------------------------------------------------------------------------------
-- Úklid
---------------------------------------------------------------------------------------------------
AddEventHandler('onResourceStop', function(resource)
    if resource ~= GetCurrentResourceName() then return end
    local names = {}
    for _, option in ipairs(pumpOptions) do names[#names + 1] = option.name end
    target:removeModel(Config.Refuel.PumpModels, names)
    local vehicleNames = {}
    for _, option in ipairs(vehicleOptions) do vehicleNames[#vehicleNames + 1] = option.name end
    target:removeGlobalVehicle(vehicleNames)
    for _, id in ipairs(registeredZones) do target:removeZone(id) end
end)
