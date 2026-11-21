--[[
    xenon_fuel – stav paliva vozidel (server)

    Princip:
      * Autoritativní hodnota je na serveru (EntityFuel) a replikuje se přes state bag 'fuel'.
      * Klient smí hodnotu pouze snižovat (spotřeba). Každé zvýšení od klienta je vráceno zpět.
      * Doplnění paliva provádí výhradně server (tankování, admin, exporty).
      * Ukládání do DB probíhá hromadně v intervalu a jen u změněných hodnot.
]]

Fuel = {}

local EntityFuel = {}       -- [netId] = fuel
local EntityPlate = {}      -- [netId] = plate
local PlateFuel = {}        -- [plate] = { fuel, saved, dirty, tracked, checking }
local OwnedCache = {}       -- [plate] = boolean
local ModelClass = {}       -- [modelHash] = class (ověřená třída modelu)
local initPending = {}      -- [netId] = true

local persistence = Config.Fuel.Persistence

-- Typ entity podle GetVehicleType (server) pro kontrolu třídy hlášené klientem
local TypeForClass = { [8] = 'bike', [13] = 'bike', [14] = 'boat', [15] = 'heli', [16] = 'plane', [21] = 'train' }
local AutomobileTypes = { automobile = true, quadbike = true, amphibious_automobile = true, amphibious_quadbike = true }

local function plateOf(entity)
    return Utils.TrimPlate(GetVehicleNumberPlateText(entity))
end

local function isOwned(plate)
    if plate == '' then return false end
    local cached = OwnedCache[plate]
    if cached ~= nil then return cached end
    local ok, owned = pcall(Bridge.IsVehicleOwned, plate)
    owned = ok and owned or false
    OwnedCache[plate] = owned
    return owned
end

local function trackPlate(entity, netId, value)
    if not Config.Features.PersistFuel then return end
    local plate = EntityPlate[netId]
    if not plate then
        plate = plateOf(entity)
        EntityPlate[netId] = plate
    end
    if plate == '' then return end

    local record = PlateFuel[plate]
    if not record then
        record = { fuel = value, saved = nil, dirty = false, tracked = nil }
        PlateFuel[plate] = record
    end
    record.fuel = value

    if record.tracked == nil then
        if not persistence.OnlyOwnedVehicles then
            record.tracked = true
        elseif not record.checking then
            record.checking = true
            CreateThread(function()
                record.tracked = isOwned(plate)
                record.checking = nil
                if record.tracked and (not record.saved or math.abs(record.saved - record.fuel) >= persistence.MinChange) then
                    record.dirty = true
                end
            end)
            return
        end
    end

    if record.tracked and (not record.saved or math.abs(record.saved - value) >= persistence.MinChange) then
        record.dirty = true
    end
end

---------------------------------------------------------------------------------------------------
-- Veřejné API
---------------------------------------------------------------------------------------------------

--- Ověří / naučí se třídu modelu a vrátí profil vozidla
---@param entity number
---@param reportedClass number|nil třída nahlášená klientem
function Fuel.GetProfile(entity, reportedClass)
    local model = Utils.Hash(GetEntityModel(entity))
    if Utils.IsModelIgnored(model) then return nil end

    local vtype = GetVehicleType(entity)
    if vtype == 'trailer' or vtype == 'train' then return nil end

    local class = ModelClass[model]
    reportedClass = Utils.ToInt(reportedClass)

    if not class and reportedClass and reportedClass >= 0 and reportedClass <= 22 then
        local expected = TypeForClass[reportedClass]
        local valid
        if expected then
            valid = vtype == expected or (reportedClass == 14 and vtype == 'submarine')
        else
            valid = vtype == nil or AutomobileTypes[vtype] == true
        end
        if valid then
            ModelClass[model] = reportedClass
            class = reportedClass
        else
            Core.Suspicious(NetworkGetEntityOwner(entity), ('nesouhlasí třída vozidla %s s typem %s'):format(reportedClass, tostring(vtype)))
        end
    elseif class and reportedClass and reportedClass ~= class then
        Utils.Debug(('Model %s: nahlášená třída %s neodpovídá uložené %s'):format(model, reportedClass, class))
    end

    if not class then
        -- Bez ověřené třídy lze určit alespoň základní kategorii z typu vozidla
        if vtype == 'bike' then class = 8
        elseif vtype == 'boat' or vtype == 'submarine' then class = 14
        elseif vtype == 'heli' then class = 15
        elseif vtype == 'plane' then class = 16
        else class = 1 end
    end

    return Utils.GetVehicleProfile(model, class)
end

function Fuel.Get(entity)
    if not entity or entity == 0 or not DoesEntityExist(entity) then return nil end
    local netId = NetworkGetNetworkIdFromEntity(entity)
    return EntityFuel[netId] or Entity(entity).state.fuel
end

--- Nastaví palivo vozidla (pouze server)
function Fuel.Set(entity, value)
    if not entity or entity == 0 or not DoesEntityExist(entity) then return false end
    value = Utils.Round(Utils.Clamp(Utils.ToNumber(value) or 0, 0, 100), 2)
    local netId = NetworkGetNetworkIdFromEntity(entity)
    EntityFuel[netId] = value
    Entity(entity).state:set('fuel', value, true)
    trackPlate(entity, netId, value)
    return true
end

--- Zajistí, že vozidlo má inicializovaný stav paliva. Vrací aktuální hodnotu.
function Fuel.Init(entity)
    if not entity or entity == 0 or not DoesEntityExist(entity) then return nil end
    local netId = NetworkGetNetworkIdFromEntity(entity)
    if EntityFuel[netId] then return EntityFuel[netId] end

    if initPending[netId] then
        local timeout = GetGameTimer() + 5000
        while initPending[netId] and GetGameTimer() < timeout do Wait(50) end
        return EntityFuel[netId]
    end

    initPending[netId] = true
    local plate = plateOf(entity)
    EntityPlate[netId] = plate
    local value

    local record = plate ~= '' and PlateFuel[plate]
    if record then
        value = record.fuel
    elseif Config.Features.PersistFuel and plate ~= '' then
        local stored = MySQL.scalar.await('SELECT fuel FROM `xenon_fuel_vehicles` WHERE plate = ?', { plate })
        if stored then
            value = tonumber(stored)
            PlateFuel[plate] = { fuel = value, saved = value, dirty = false, tracked = true }
        end
    end

    if not value then
        if plate ~= '' and isOwned(plate) then
            value = Config.Fuel.DefaultOwned
        else
            value = math.random(Config.Fuel.DefaultRandom.min, Config.Fuel.DefaultRandom.max)
        end
    end

    if DoesEntityExist(entity) then
        Fuel.Set(entity, value)
    end
    initPending[netId] = nil
    return EntityFuel[netId]
end

--- Nastaví poslední natankovaný druh paliva (ovlivňuje spotřebu)
function Fuel.SetFuelType(entity, fuelType)
    if DoesEntityExist(entity) and Config.FuelTypes[fuelType] then
        Entity(entity).state:set('fuelType', fuelType, true)
    end
end

function Fuel.GetPlateFuel(plate)
    plate = Utils.TrimPlate(plate)
    local record = PlateFuel[plate]
    if record then return record.fuel end
    if not Config.Features.PersistFuel then return nil end
    local stored = MySQL.scalar.await('SELECT fuel FROM `xenon_fuel_vehicles` WHERE plate = ?', { plate })
    return stored and tonumber(stored) or nil
end

function Fuel.SetPlateFuel(plate, value)
    plate = Utils.TrimPlate(plate)
    if plate == '' then return false end
    value = Utils.Round(Utils.Clamp(Utils.ToNumber(value) or 0, 0, 100), 2)
    local record = PlateFuel[plate]
    if not record then
        record = { fuel = value, saved = nil, dirty = true, tracked = true }
        PlateFuel[plate] = record
    else
        record.fuel = value
        record.tracked = true
        record.dirty = true
    end
    -- aktualizace existující entity se stejnou SPZ
    for netId, p in pairs(EntityPlate) do
        if p == plate then
            local entity = NetworkGetEntityFromNetworkId(netId)
            if entity ~= 0 and DoesEntityExist(entity) then Fuel.Set(entity, value) end
        end
    end
    return true
end

---------------------------------------------------------------------------------------------------
-- Ukládání
---------------------------------------------------------------------------------------------------
function Fuel.Flush(async)
    if not Config.Features.PersistFuel then return 0 end
    local values, params, count = {}, {}, 0

    local function send()
        if #values == 0 then return end
        local query = ('INSERT INTO `xenon_fuel_vehicles` (plate, fuel) VALUES %s ON DUPLICATE KEY UPDATE fuel = VALUES(fuel)')
            :format(table.concat(values, ','))
        if async then
            MySQL.query(query, params)
        else
            MySQL.query.await(query, params)
        end
        values, params = {}, {}
    end

    for plate, record in pairs(PlateFuel) do
        if record.dirty and record.tracked then
            values[#values + 1] = '(?, ?)'
            params[#params + 1] = plate
            params[#params + 1] = record.fuel
            record.saved = record.fuel
            record.dirty = false
            count = count + 1
            if #values >= 250 then send() end
        end
    end
    send()

    if count > 0 then Utils.Debug(('Uloženo palivo %d vozidel'):format(count)) end
    return count
end

---------------------------------------------------------------------------------------------------
-- Ochrana state bagu – klient smí palivo jen snižovat
---------------------------------------------------------------------------------------------------
AddStateBagChangeHandler('fuel', nil, function(bagName, _, value)
    local entity = GetEntityFromStateBagName(bagName)
    if not entity or entity == 0 then return end
    local netId = NetworkGetNetworkIdFromEntity(entity)
    local current = EntityFuel[netId]

    if value == current then return end -- změna provedená serverem

    if current == nil then
        -- vozidlo ještě nebylo inicializováno serverem – hodnota od klienta se ignoruje
        CreateThread(function()
            Wait(0)
            if DoesEntityExist(entity) then Fuel.Init(entity) end
        end)
        return
    end

    local number = Utils.ToNumber(value)
    if not number or number < 0 or number > 100
        or (Config.Security.RejectClientFuelIncrease and number > current + 0.01) then
        if number and number > current then
            Core.Suspicious(NetworkGetEntityOwner(entity), ('pokus o zvýšení paliva %.2f -> %.2f'):format(current, number))
        end
        SetTimeout(0, function()
            if DoesEntityExist(entity) and EntityFuel[netId] then
                Entity(entity).state:set('fuel', EntityFuel[netId], true)
            end
        end)
        return
    end

    number = Utils.Round(number, 2)
    EntityFuel[netId] = number
    trackPlate(entity, netId, number)
end)

AddEventHandler('entityRemoved', function(entity)
    local netId = NetworkGetNetworkIdFromEntity(entity)
    if not netId or not EntityFuel[netId] then return end
    local plate = EntityPlate[netId]
    EntityFuel[netId] = nil
    EntityPlate[netId] = nil
    initPending[netId] = nil
    if plate then
        local record = PlateFuel[plate]
        if record and record.tracked == false then
            PlateFuel[plate] = nil
            OwnedCache[plate] = nil
        end
    end
end)

---------------------------------------------------------------------------------------------------
-- Callbacky
---------------------------------------------------------------------------------------------------
Core.RegisterCallback('initVehicle', function(source, netId, class)
    if not Core.Throttle(source, 'initVehicle', 200) then return nil end
    netId = Utils.ToInt(netId)
    if not netId then return nil end
    local entity = NetworkGetEntityFromNetworkId(netId)
    if not entity or entity == 0 or not DoesEntityExist(entity) or GetEntityType(entity) ~= 2 then return nil end

    local dist = Core.PlayerDistance(source, GetEntityCoords(entity))
    if not dist or dist > 25.0 then return nil end

    local profile = Fuel.GetProfile(entity, class)
    if not profile then return nil end
    return Fuel.Init(entity)
end)

---------------------------------------------------------------------------------------------------
-- Smyčka ukládání
---------------------------------------------------------------------------------------------------
function Fuel.StartSaveLoop()
    if not Config.Features.PersistFuel then return end
    CreateThread(function()
        while true do
            Wait(math.max(1, persistence.SaveInterval) * 60000)
            Fuel.Flush(false)
        end
    end)
end

---------------------------------------------------------------------------------------------------
-- Exporty pro ostatní server-side scripty (garáže apod.)
---------------------------------------------------------------------------------------------------
local function resolveEntity(vehicle)
    if type(vehicle) ~= 'number' then return nil end
    if DoesEntityExist(vehicle) then return vehicle end
    local entity = NetworkGetEntityFromNetworkId(vehicle)
    if entity and entity ~= 0 and DoesEntityExist(entity) then return entity end
    return nil
end

exports('GetFuel', function(vehicle)
    local entity = resolveEntity(vehicle)
    return entity and Fuel.Get(entity) or nil
end)

exports('SetFuel', function(vehicle, value)
    local entity = resolveEntity(vehicle)
    if not entity then return false end
    return Fuel.Set(entity, value)
end)

exports('GetPlateFuel', Fuel.GetPlateFuel)
exports('SetPlateFuel', Fuel.SetPlateFuel)
