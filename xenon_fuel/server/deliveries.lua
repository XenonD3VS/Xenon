--[[
    xenon_fuel – objednávky paliva a rozvoz cisternami
]]

Deliveries = {
    orders = {},    -- aktivní objednávky [id] = order (pending / assigned / loaded)
    jobs = {},      -- aktivní rozvozové zakázky [source] = job
}

local ACTIVE = { pending = true, assigned = true, loaded = true }
local orderCfg = Config.Orders
local jobCfg = Config.TankerJob

local function ordersEnabled()
    return Config.Features.Orders and Config.Features.Ownership
end

local function tankerEnabled()
    return ordersEnabled() and Config.Features.TankerJob and orderCfg.Methods.tanker.enabled
end

local function rowToOrder(row)
    return {
        id = row.id,
        stationId = row.station_id,
        fuelType = row.fuel_type,
        liters = tonumber(row.liters) or 0,
        cost = tonumber(row.cost) or 0,
        reward = tonumber(row.reward) or 0,
        method = row.method,
        status = row.status,
        orderedBy = row.ordered_by,
        orderedByName = row.ordered_by_name,
        driver = row.driver,
        driverName = row.driver_name,
        createdAt = tonumber(row.created_at) or os.time(),
        deliverAt = tonumber(row.deliver_at) or 0,
        deliveredAt = tonumber(row.delivered_at),
    }
end

local function saveOrder(order)
    MySQL.update(
        'UPDATE `xenon_fuel_orders` SET status = ?, driver = ?, driver_name = ?, deliver_at = ?, delivered_at = ? WHERE id = ?',
        { order.status, order.driver, order.driverName, order.deliverAt, order.deliveredAt, order.id }
    )
end

function Deliveries.Load()
    local rows = MySQL.query.await("SELECT * FROM `xenon_fuel_orders` WHERE status IN ('pending', 'assigned', 'loaded')") or {}
    for _, row in ipairs(rows) do
        local order = rowToOrder(row)
        if order.status ~= 'pending' then
            -- po restartu serveru vozidla neexistují – zakázka se vrací do nabídky
            order.status = 'pending'
            order.driver, order.driverName = nil, nil
            saveOrder(order)
        end
        Deliveries.orders[order.id] = order
    end
    Utils.Debug(('Načteno %d aktivních objednávek'):format(Utils.TableCount(Deliveries.orders)))
end

--- Množství paliva, které je již objednané a na cestě
function Deliveries.PendingLiters(stationId, fuelType)
    local total = 0
    for _, order in pairs(Deliveries.orders) do
        if order.stationId == stationId and order.fuelType == fuelType then total = total + order.liters end
    end
    return total
end

function Deliveries.CountActive(stationId)
    local count = 0
    for _, order in pairs(Deliveries.orders) do
        if order.stationId == stationId then count = count + 1 end
    end
    return count
end

--- Výpočet ceny objednávky (stejný vzorec používá i UI pro náhled)
function Deliveries.Quote(fuelType, liters, method)
    local fuel = Config.FuelTypes[fuelType]
    if not fuel then return nil end
    if method == 'supplier' then
        return math.ceil(liters * (fuel.wholesale + orderCfg.Methods.supplier.feePerLiter) - 1e-9), 0
    elseif method == 'tanker' then
        local r = orderCfg.Methods.tanker.reward
        local reward = math.floor(math.min(r.max, r.base + liters * r.perLiter))
        return math.ceil(liters * fuel.wholesale - 1e-9) + reward, reward
    end
    return nil
end

local function notifyStation(station, message, notifyType)
    local ownerSource = station.owner and Bridge.GetSourceFromIdentifier(station.owner)
    if ownerSource then Core.Notify(ownerSource, message, notifyType) end
end

---------------------------------------------------------------------------------------------------
-- Objednávky
---------------------------------------------------------------------------------------------------
function Deliveries.CreateOrder(source, station, fuelType, liters, method)
    if not ordersEnabled() then return Core.Fail('error_feature_disabled') end
    if not Stations.IsOwned(station) then return Core.Fail('error_not_owned') end
    if type(fuelType) ~= 'string' or not station.cfg.fuelSet[fuelType] then return Core.Fail('error_invalid_fuel') end
    if method ~= 'supplier' and method ~= 'tanker' then return Core.Fail('error_invalid_method') end
    if method == 'supplier' and not orderCfg.Methods.supplier.enabled then return Core.Fail('error_invalid_method') end
    if method == 'tanker' and not tankerEnabled() then return Core.Fail('error_invalid_method') end

    liters = Utils.ToInt(liters)
    if not liters or liters < orderCfg.MinLiters or liters > orderCfg.MaxLiters then
        return Core.Fail('error_order_amount', orderCfg.MinLiters, orderCfg.MaxLiters)
    end
    if Deliveries.CountActive(station.id) >= orderCfg.MaxPendingPerStation then
        return Core.Fail('error_max_orders', orderCfg.MaxPendingPerStation)
    end

    local capacity = station.cfg.capacity[fuelType]
    local free = capacity - (station.stock[fuelType] or 0) - Deliveries.PendingLiters(station.id, fuelType)
    if liters > math.floor(free) then
        return Core.Fail('error_order_capacity', Utils.FormatNumber(math.max(0, math.floor(free))))
    end

    local cost, reward = Deliveries.Quote(fuelType, liters, method)
    local identifier, name = Bridge.GetIdentifier(source), Bridge.GetName(source)
    local fuel = Config.FuelTypes[fuelType]
    local note = ('%s %s %s (%s)'):format(Utils.FormatNumber(liters), fuel.unit, fuel.label, L('order_method_' .. method))

    -- platba z firemního účtu (atomicky)
    if not Stations.Debit(station, cost, 'order', identifier, name, note, true) then
        return Core.Fail('error_company_funds', Utils.FormatMoney(cost))
    end

    local now = os.time()
    local deliverAt = 0
    if method == 'supplier' then
        deliverAt = now + orderCfg.Methods.supplier.delayMinutes * 60
    elseif orderCfg.Methods.tanker.fallbackToSupplierAfter > 0 then
        deliverAt = now + orderCfg.Methods.tanker.fallbackToSupplierAfter * 60
    end

    local order = {
        id = nil, stationId = station.id, fuelType = fuelType, liters = liters, cost = cost, reward = reward,
        method = method, status = 'pending', orderedBy = identifier, orderedByName = name,
        createdAt = now, deliverAt = deliverAt,
    }

    -- rezervace kapacity v paměti před zápisem do DB
    local tempKey = 'tmp:' .. now .. ':' .. math.random(1, 1e6)
    Deliveries.orders[tempKey] = order

    local id = MySQL.insert.await(
        'INSERT INTO `xenon_fuel_orders` (station_id, fuel_type, liters, cost, reward, method, status, ordered_by, ordered_by_name, created_at, deliver_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        { station.id, fuelType, liters, cost, reward, method, 'pending', identifier, name, now, deliverAt }
    )
    Deliveries.orders[tempKey] = nil

    if not id then
        Stations.Credit(station, cost, 'order_refund', identifier, name, note)
        station.stats.costs = math.max(0, station.stats.costs - cost)
        return Core.Fail('error_internal')
    end

    order.id = id
    Deliveries.orders[id] = order
    return Core.Success({ id = id }, 'order_created', Utils.FormatNumber(liters), fuel.unit, fuel.label, Utils.FormatMoney(cost))
end

local function refundOrder(station, order, actor, actorName, note)
    if station and order.cost > 0 then
        Stations.Credit(station, order.cost, 'order_refund', actor, actorName, note)
        station.stats.costs = math.max(0, station.stats.costs - order.cost)
        Stations.Save(station)
    end
end

function Deliveries.CancelOrder(source, station, orderId)
    orderId = Utils.ToInt(orderId)
    local order = orderId and Deliveries.orders[orderId]
    if not order or order.stationId ~= station.id then return Core.Fail('error_order_not_found') end
    if order.status ~= 'pending' then return Core.Fail('error_order_in_progress') end

    Deliveries.orders[orderId] = nil
    order.status = 'cancelled'
    saveOrder(order)
    refundOrder(station, order, Bridge.GetIdentifier(source), Bridge.GetName(source), L('finance_note_order_cancel', order.id))
    return Core.Success(nil, 'order_cancelled', order.id)
end

--- Zruší všechny aktivní objednávky benzinky (prodej / reset). Peníze se vrací na firemní účet.
function Deliveries.CancelStationOrders(station, actor, actorName)
    local ids = {}
    for id, order in pairs(Deliveries.orders) do
        if order.stationId == station.id then ids[#ids + 1] = id end
    end
    for _, id in ipairs(ids) do
        local order = Deliveries.orders[id]
        Deliveries.orders[id] = nil
        -- ukončení rozvozu, pokud je zakázka na cestě
        for source, job in pairs(Deliveries.jobs) do
            if job.orderId == id then
                Deliveries.EndJob(source, 'station_sold')
            end
        end
        order.status = 'cancelled'
        saveOrder(order)
        refundOrder(station, order, actor, actorName, L('finance_note_order_cancel', order.id))
    end
end

--- Dokončí doručení objednávky – kontrola kapacity a naskladnění
function Deliveries.Complete(order, via)
    Deliveries.orders[order.id] = nil
    local station = Stations.Get(order.stationId)
    local now = os.time()

    if not station or not Stations.IsOwned(station) then
        order.status = 'cancelled'
        saveOrder(order)
        return 0
    end

    local fuel = Config.FuelTypes[order.fuelType]
    local capacity = station.cfg.capacity[order.fuelType] or 0
    local stock = station.stock[order.fuelType] or 0
    local delivered = math.max(0, math.min(order.liters, math.floor(capacity - stock)))
    local excess = order.liters - delivered

    station.stock[order.fuelType] = stock + delivered
    if excess > 0 then
        local refund = math.floor(excess * fuel.wholesale)
        if refund > 0 then
            Stations.Credit(station, refund, 'order_refund', nil, 'System', L('finance_note_order_excess', order.id, Utils.FormatNumber(excess), fuel.unit))
            station.stats.costs = math.max(0, station.stats.costs - refund)
        end
    end
    Stations.Save(station)

    order.status = 'delivered'
    order.deliveredAt = now
    saveOrder(order)

    notifyStation(station, L('order_delivered_owner', order.id, Utils.FormatNumber(delivered), fuel.unit, fuel.label, Stations.GetLabel(station)), 'success')
    Utils.Debug(('Objednávka #%d doručena (%s): %d %s'):format(order.id, via, delivered, order.fuelType))
    return delivered
end

local function endJobForOrder(orderId, reason)
    for source, job in pairs(Deliveries.jobs) do
        if job.orderId == orderId then Deliveries.EndJob(source, reason) end
    end
end

--- Admin: okamžité doručení objednávky (případný rozvoz se ukončí)
function Deliveries.ForceDeliver(order)
    endJobForOrder(order.id, 'admin')
    return Deliveries.Complete(order, 'admin')
end

--- Admin: zrušení objednávky v jakémkoliv stavu, peníze se vrátí na firemní účet
function Deliveries.ForceCancel(order, actor, actorName)
    endJobForOrder(order.id, 'admin')
    Deliveries.orders[order.id] = nil
    order.status = 'cancelled'
    saveOrder(order)
    refundOrder(Stations.Get(order.stationId), order, actor, actorName, L('finance_note_order_cancel', order.id))
end

--- Objednávky pro management (aktivní + posledních 10 uzavřených)
function Deliveries.GetStationOrders(stationId)
    local list = {}
    for _, order in pairs(Deliveries.orders) do
        if order.stationId == stationId and order.id then
            list[#list + 1] = {
                id = order.id, fuelType = order.fuelType, liters = order.liters, cost = order.cost, method = order.method,
                status = order.status, driverName = order.driverName, orderedByName = order.orderedByName,
                createdAt = order.createdAt, deliverAt = order.deliverAt,
            }
        end
    end
    local rows = MySQL.query.await(
        "SELECT * FROM `xenon_fuel_orders` WHERE station_id = ? AND status IN ('delivered', 'cancelled') ORDER BY id DESC LIMIT 10",
        { stationId }
    ) or {}
    for _, row in ipairs(rows) do
        local order = rowToOrder(row)
        list[#list + 1] = {
            id = order.id, fuelType = order.fuelType, liters = order.liters, cost = order.cost, method = order.method,
            status = order.status, driverName = order.driverName, orderedByName = order.orderedByName,
            createdAt = order.createdAt, deliveredAt = order.deliveredAt,
        }
    end
    table.sort(list, function(a, b) return a.id > b.id end)
    return list
end

local function processOrders()
    local now = os.time()
    for _, order in pairs(Deliveries.orders) do
        if order.id and order.status == 'pending' and order.deliverAt > 0 and now >= order.deliverAt then
            Deliveries.Complete(order, 'supplier')
        end
    end
end

---------------------------------------------------------------------------------------------------
-- Rozvoz cisternami
---------------------------------------------------------------------------------------------------
local depot = jobCfg.Depot

local function deleteEntity(entity)
    if entity and entity ~= 0 and DoesEntityExist(entity) then DeleteEntity(entity) end
end

local function jobPayload(job)
    if not job then return nil end
    local order = Deliveries.orders[job.orderId]
    local station = order and Stations.Get(order.stationId)
    local fuel = order and Config.FuelTypes[order.fuelType]
    return {
        orderId = job.orderId,
        status = job.status,
        truckNet = job.truckNet,
        trailerNet = job.trailerNet,
        liters = job.liters,
        reward = job.reward,
        fuel = fuel and { id = order.fuelType, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit } or nil,
        station = station and {
            id = station.id,
            label = Stations.GetLabel(station),
            coords = station.cfg.unloadPoint,
            radius = station.cfg.unloadRadius,
        } or nil,
    }
end

--- Ukončí zakázku řidiče a odstraní vozidla
---@param reason string completed | cancelled | failed | timeout | station_sold | disconnected | returned
function Deliveries.EndJob(source, reason)
    local job = Deliveries.jobs[source]
    if not job then return end
    Deliveries.jobs[source] = nil

    deleteEntity(job.trailer)
    deleteEntity(job.truck)

    -- nedoručená objednávka se vrací do nabídky
    local order = Deliveries.orders[job.orderId]
    if order and job.status ~= 'delivered' and reason ~= 'station_sold' then
        order.status = 'pending'
        order.driver, order.driverName = nil, nil
        saveOrder(order)
    end

    if reason ~= 'disconnected' then
        TriggerClientEvent('xenon_fuel:client:jobEnded', source, reason)
    end
end

local function isNearDepot(source, distance)
    local dist = Core.PlayerDistance(source, depot.coords)
    return dist and dist <= (distance or 30.0)
end

Core.RegisterCallback('getJobBoard', function(source)
    if not tankerEnabled() then return Core.Fail('error_feature_disabled') end
    if not isNearDepot(source, 30.0) then return Core.Fail('error_not_at_depot') end

    local list = {}
    for _, order in pairs(Deliveries.orders) do
        if order.id and order.method == 'tanker' and order.status == 'pending' then
            local station = Stations.Get(order.stationId)
            local fuel = Config.FuelTypes[order.fuelType]
            if station and fuel then
                list[#list + 1] = {
                    id = order.id,
                    station = Stations.GetLabel(station),
                    distance = math.floor(#(station.cfg.coords - depot.coords)),
                    fuel = { id = order.fuelType, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit },
                    liters = order.liters,
                    reward = order.reward,
                    createdAt = order.createdAt,
                }
            end
        end
    end
    table.sort(list, function(a, b) return a.id < b.id end)

    local requiredJob = jobCfg.RequiredJob
    return Core.Success({
        orders = list,
        job = jobPayload(Deliveries.jobs[source]),
        canWork = not requiredJob or Bridge.GetJob(source) == requiredJob,
        depot = depot.label,
    })
end)

local function spawnServerVehicle(model, vehicleType, coords, heading)
    local entity = CreateVehicleServerSetter(GetHashKey(model), vehicleType, coords.x, coords.y, coords.z, heading)
    local timeout = GetGameTimer() + 4000
    while (not entity or entity == 0 or not DoesEntityExist(entity)) and GetGameTimer() < timeout do Wait(50) end
    if not entity or entity == 0 or not DoesEntityExist(entity) then return nil end
    return entity
end

local function isAreaClear(coords, radius)
    for _, vehicle in ipairs(GetAllVehicles()) do
        if #(GetEntityCoords(vehicle) - coords) < radius then return false end
    end
    return true
end

Core.RegisterCallback('acceptJob', function(source, orderId)
    if not tankerEnabled() then return Core.Fail('error_feature_disabled') end
    if not Core.Throttle(source, 'acceptJob', 3000) then return Core.Fail('error_too_fast') end
    if not isNearDepot(source, 30.0) then return Core.Fail('error_not_at_depot') end
    if Deliveries.jobs[source] then return Core.Fail('error_job_active') end
    if jobCfg.RequiredJob and Bridge.GetJob(source) ~= jobCfg.RequiredJob then return Core.Fail('error_wrong_job') end

    orderId = Utils.ToInt(orderId)
    local order = orderId and Deliveries.orders[orderId]
    if not order or order.method ~= 'tanker' or order.status ~= 'pending' then return Core.Fail('error_order_taken') end

    local spawn = depot.vehicleSpawn
    local spawnCoords = vector3(spawn.x, spawn.y, spawn.z)
    local heading = spawn.w
    local rad = math.rad(heading)
    local forward = vector3(-math.sin(rad), math.cos(rad), 0.0)
    local trailerCoords = spawnCoords - forward * 10.5

    if not isAreaClear(spawnCoords, 6.0) or not isAreaClear(trailerCoords, 7.0) then
        return Core.Fail('error_spawn_blocked')
    end

    -- přidělení zakázky ještě před spawnem (yield) – nikdo jiný ji nemůže převzít
    local identifier, name = Bridge.GetIdentifier(source), Bridge.GetName(source)
    order.status = 'assigned'
    order.driver, order.driverName = identifier, name

    local truck = spawnServerVehicle(jobCfg.Vehicles.truck, 'automobile', spawnCoords, heading)
    local trailer = truck and spawnServerVehicle(jobCfg.Vehicles.trailer, 'trailer', trailerCoords, heading)

    if not truck or not trailer or not Bridge.GetPlayer(source) then
        deleteEntity(truck)
        deleteEntity(trailer)
        order.status = 'pending'
        order.driver, order.driverName = nil, nil
        return Core.Fail('error_spawn_failed')
    end

    saveOrder(order)

    local job = {
        orderId = order.id,
        truck = truck,
        trailer = trailer,
        truckNet = NetworkGetNetworkIdFromEntity(truck),
        trailerNet = NetworkGetNetworkIdFromEntity(trailer),
        status = 'assigned',
        liters = order.liters,
        reward = order.reward,
        startedAt = os.time(),
    }
    Deliveries.jobs[source] = job

    Entity(trailer).state:set('xenonTanker', source, true)
    Fuel.Set(truck, 100)
    local ped = GetPlayerPed(source)
    if ped and ped ~= 0 then SetPedIntoVehicle(ped, truck, -1) end

    return Core.Success(jobPayload(job), 'job_accepted', order.id)
end)

local function getJob(source, expectedStatus)
    local job = Deliveries.jobs[source]
    if not job then return nil, 'error_no_job' end
    if expectedStatus and job.status ~= expectedStatus then return nil, 'error_job_state' end
    if not DoesEntityExist(job.trailer) then return nil, 'error_trailer_missing' end
    local order = Deliveries.orders[job.orderId]
    if not order or order.driver ~= Bridge.GetIdentifier(source) then return nil, 'error_no_job' end
    return job, nil, order
end

local function playerNearTrailer(source, job)
    local dist = Core.PlayerDistance(source, GetEntityCoords(job.trailer))
    return dist and dist <= 14.0
end

Core.RegisterCallback('beginLoad', function(source)
    local job, err = getJob(source, 'assigned')
    if not job then return Core.Fail(err) end
    local loading = depot.loading
    if #(GetEntityCoords(job.trailer) - loading.coords) > loading.radius then return Core.Fail('error_not_at_loading') end
    if not playerNearTrailer(source, job) then return Core.Fail('error_too_far_trailer') end
    job.loadStart = GetGameTimer()
    return Core.Success({ duration = jobCfg.LoadTime })
end)

Core.RegisterCallback('finishLoad', function(source)
    local job, err, order = getJob(source, 'assigned')
    if not job then return Core.Fail(err) end
    if not job.loadStart or GetGameTimer() - job.loadStart < (jobCfg.LoadTime - 1) * 1000 then
        Core.Suspicious(source, 'dokončení nakládky před uplynutím času')
        return Core.Fail('error_too_fast')
    end
    if #(GetEntityCoords(job.trailer) - depot.loading.coords) > depot.loading.radius then return Core.Fail('error_not_at_loading') end

    job.status = 'loaded'
    job.loadStart = nil
    order.status = 'loaded'
    saveOrder(order)
    return Core.Success(jobPayload(job), 'job_loaded')
end)

local function unloadDuration(liters)
    local limits = jobCfg.UnloadTimeLimits
    return math.floor(Utils.Clamp(liters / 1000 * jobCfg.UnloadTimePer1000, limits.min, limits.max))
end

Core.RegisterCallback('beginUnload', function(source)
    local job, err, order = getJob(source, 'loaded')
    if not job then return Core.Fail(err) end
    local station = Stations.Get(order.stationId)
    if not station then return Core.Fail('error_invalid_station') end
    if #(GetEntityCoords(job.trailer) - station.cfg.unloadPoint) > station.cfg.unloadRadius then
        return Core.Fail('error_not_at_unload')
    end
    if not playerNearTrailer(source, job) then return Core.Fail('error_too_far_trailer') end
    job.unloadStart = GetGameTimer()
    job.unloadDuration = unloadDuration(job.liters)
    return Core.Success({ duration = job.unloadDuration })
end)

Core.RegisterCallback('finishUnload', function(source)
    local job, err, order = getJob(source, 'loaded')
    if not job then return Core.Fail(err) end
    if not job.unloadStart or GetGameTimer() - job.unloadStart < (job.unloadDuration - 1) * 1000 then
        Core.Suspicious(source, 'dokončení vykládky před uplynutím času')
        return Core.Fail('error_too_fast')
    end
    local station = Stations.Get(order.stationId)
    if not station or #(GetEntityCoords(job.trailer) - station.cfg.unloadPoint) > station.cfg.unloadRadius then
        return Core.Fail('error_not_at_unload')
    end

    -- nejdřív označit jako doručené (ochrana proti opakovanému vyplacení)
    job.status = 'delivered'
    job.unloadStart = nil
    job.deliveredAt = os.time()

    local delivered = Deliveries.Complete(order, 'tanker')
    local reward = order.reward
    if reward > 0 then
        Bridge.AddMoney(source, 'bank', reward, 'xenon_fuel_delivery')
    end

    deleteEntity(job.trailer)
    job.trailer = nil

    local fuel = Config.FuelTypes[order.fuelType]
    return Core.Success({ delivered = delivered, reward = reward }, 'job_delivered',
        Utils.FormatNumber(delivered), fuel.unit, Utils.FormatMoney(reward))
end)

Core.RegisterCallback('returnVehicle', function(source)
    local job = Deliveries.jobs[source]
    if not job then return Core.Fail('error_no_job') end
    local truckOk = job.truck and DoesEntityExist(job.truck)
    if truckOk and #(GetEntityCoords(job.truck) - depot.coords) > depot.returnRadius then
        return Core.Fail('error_truck_not_at_depot')
    end
    if not isNearDepot(source, depot.returnRadius) then return Core.Fail('error_not_at_depot') end
    local wasDelivered = job.status == 'delivered'
    Deliveries.EndJob(source, wasDelivered and 'returned' or 'cancelled')
    return Core.Success(nil, wasDelivered and 'job_returned' or 'job_cancelled')
end)

Core.RegisterCallback('cancelJob', function(source)
    local job = Deliveries.jobs[source]
    if not job then return Core.Fail('error_no_job') end
    Deliveries.EndJob(source, 'cancelled')
    return Core.Success(nil, 'job_cancelled')
end)

local function monitorJobs()
    local now = os.time()
    for source, job in pairs(Deliveries.jobs) do
        if job.status == 'delivered' then
            if now - (job.deliveredAt or now) > 15 * 60 then
                Deliveries.EndJob(source, 'returned')
            end
        elseif not job.trailer or not DoesEntityExist(job.trailer) then
            Deliveries.EndJob(source, 'failed')
        elseif now - job.startedAt > jobCfg.JobTimeout * 60 then
            Deliveries.EndJob(source, 'timeout')
        end
    end
end

---------------------------------------------------------------------------------------------------
-- Smyčky
---------------------------------------------------------------------------------------------------
function Deliveries.StartLoops()
    if not ordersEnabled() then return end
    CreateThread(function()
        while true do
            Wait(math.max(10, orderCfg.ProcessInterval) * 1000)
            local ok, err = pcall(processOrders)
            if not ok then print(('^1[xenon_fuel] Chyba při zpracování objednávek: %s^7'):format(tostring(err))) end
        end
    end)
    if tankerEnabled() then
        CreateThread(function()
            while true do
                Wait(5000)
                if next(Deliveries.jobs) then
                    local ok, err = pcall(monitorJobs)
                    if not ok then print(('^1[xenon_fuel] Chyba při kontrole rozvozů: %s^7'):format(tostring(err))) end
                end
            end
        end)
    end
end

function Deliveries.EndAllJobs()
    for source in pairs(Deliveries.jobs) do
        Deliveries.EndJob(source, 'cancelled')
    end
end

local function onDrop(source)
    if Deliveries.jobs[source] then Deliveries.EndJob(source, 'disconnected') end
end
Bridge.OnPlayerDropped(onDrop)
AddEventHandler('playerDropped', function() onDrop(source) end)
