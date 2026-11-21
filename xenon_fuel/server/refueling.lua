--[[
    xenon_fuel – tankování (server)

    Bezpečnostní model:
      * Cena, množství, kapacita nádrže i aktuální stav paliva se počítají výhradně na serveru.
      * Při potvrzení se odečte záloha za požadované množství (escrow) – hráč tak nemůže během
        tankování "schovat" peníze. Po skončení se nevyčerpaná část okamžitě vrátí.
      * Průběh tankování běží na serveru podle času a rychlosti čerpadla, klient jen zobrazuje.
      * Každá relace se uzavře právě jednou (ochrana proti dvojímu vyúčtování).
      * Jedno vozidlo může tankovat jen jeden hráč a jeden hráč jen jedno vozidlo.
]]

Refuel = {
    sessions = {},      -- [sessionId] = session
    byPlayer = {},      -- [source] = sessionId | 'pending'
    byVehicle = {},     -- [netId] = sessionId | 'pending'
}

local nextSessionId = 0
local loopRunning = false
local receiptItemAvailable = nil

local function hasReceiptItem()
    if receiptItemAvailable == nil then
        local ok, item = pcall(function() return exports.ox_inventory:Items('fuel_receipt') end)
        receiptItemAvailable = ok and item ~= nil
        if not receiptItemAvailable and Config.Features.Receipts then
            print('^3[xenon_fuel] Item "fuel_receipt" v ox_inventory neexistuje – účtenky se zobrazí pouze v UI. Viz README.^7')
        end
    end
    return receiptItemAvailable
end

--- Najde souřadnice stojanu – u ručně definovaných stojanů podle indexu, jinak ověří souřadnice od klienta
local function resolvePump(station, pump)
    if type(pump) ~= 'table' then return nil end
    if type(station.cfg.pumps) == 'table' then
        local entry = station.cfg.pumps[Utils.ToInt(pump.index) or -1]
        if not entry then return nil end
        return entry.coords, entry
    end
    local x, y, z = Utils.ToNumber(pump.x), Utils.ToNumber(pump.y), Utils.ToNumber(pump.z)
    if not x or not y or not z then return nil end
    local coords = vector3(x, y, z)
    if #(coords - station.cfg.coords) > station.cfg.radius + 3.0 then return nil end
    return coords, nil
end

local function getVehicleEntity(netId)
    netId = Utils.ToInt(netId)
    if not netId then return nil end
    local entity = NetworkGetEntityFromNetworkId(netId)
    if not entity or entity == 0 or not DoesEntityExist(entity) or GetEntityType(entity) ~= 2 then return nil end
    return entity, netId
end

local function fuelsForPump(station, pumpEntry)
    return (pumpEntry and pumpEntry.fuelTypes) or station.cfg.fuelTypes
end

local function paymentMethods()
    local list = {}
    for method, enabled in pairs(Config.Payment.Methods) do
        if enabled then list[#list + 1] = method end
    end
    table.sort(list)
    return list
end

--- Společné ověření polohy hráče, vozidla a stojanu
local function validatePosition(source, station, pumpCoords, entity)
    local ped = GetPlayerPed(source)
    if not ped or ped == 0 then return 'error_no_player' end
    local playerCoords = GetEntityCoords(ped)

    if #(playerCoords - pumpCoords) > Config.Refuel.HoseLength + 0.5 then return 'error_too_far_pump' end
    if GetVehiclePedIsIn(ped, false) ~= 0 then return 'error_in_vehicle' end

    local vehicleCoords = GetEntityCoords(entity)
    if #(vehicleCoords - pumpCoords) > Config.Refuel.MaxVehiclePumpDistance then return 'error_vehicle_not_at_pump' end
    if #(playerCoords - vehicleCoords) > Config.Refuel.MaxPlayerVehicleDistance + 1.5 then return 'error_too_far_vehicle' end
    if #GetEntityVelocity(entity) > Config.Refuel.MaxVehicleSpeed then return 'error_vehicle_moving' end
    if GetPedInVehicleSeat(entity, -1) ~= 0 then return 'error_vehicle_has_driver' end
    if GetIsVehicleEngineRunning(entity) then return 'error_engine_running' end
    return nil
end

---------------------------------------------------------------------------------------------------
-- Nabídka (data pro tankovací UI)
---------------------------------------------------------------------------------------------------
Core.RegisterCallback('getRefuelQuote', function(source, stationId, pump, netId, class)
    if not Core.Throttle(source, 'quote', 400) then return Core.Fail('error_too_fast') end

    local station = Stations.Get(stationId)
    if not station then return Core.Fail('error_invalid_station') end
    if not station.open then return Core.Fail('error_station_closed') end

    local pumpCoords, pumpEntry = resolvePump(station, pump)
    if not pumpCoords then return Core.Fail('error_invalid_pump') end

    local entity, vehicleNet = getVehicleEntity(netId)
    if not entity then return Core.Fail('error_no_vehicle') end
    if Refuel.byVehicle[vehicleNet] and Refuel.byVehicle[vehicleNet] ~= Refuel.byPlayer[source] then
        return Core.Fail('error_vehicle_busy')
    end

    local positionError = validatePosition(source, station, pumpCoords, entity)
    if positionError then return Core.Fail(positionError) end

    local profile = Fuel.GetProfile(entity, class)
    if not profile then return Core.Fail('error_no_fuel_vehicle') end

    local current = Fuel.Init(entity) or 0
    local maxAmount = Utils.Floor(profile.capacity * (100 - current) / 100, 2)
    local fuelType = Entity(entity).state.fuelType

    local fuels, defaultFuel = {}, nil
    for _, ft in ipairs(fuelsForPump(station, pumpEntry)) do
        local fuel = Config.FuelTypes[ft]
        local stock = Stations.GetStock(station, ft)
        local compatible = profile.fuelSet[ft] == true
        fuels[#fuels + 1] = {
            id = ft,
            label = fuel.label,
            short = fuel.short,
            color = fuel.color,
            unit = fuel.unit,
            price = Stations.GetPrice(station, ft),
            available = stock == math.huge and -1 or Utils.Floor(stock, 2),
            compatible = compatible,
        }
        if compatible and stock >= Config.Refuel.MinAmount and (not defaultFuel or ft == fuelType) then
            defaultFuel = ft
        end
    end

    local balances = {}
    for _, method in ipairs(paymentMethods()) do
        balances[method] = Bridge.GetMoney(source, method)
    end

    return Core.Success({
        station = { id = station.id, label = Stations.GetLabel(station) },
        vehicle = {
            plate = Utils.TrimPlate(GetVehicleNumberPlateText(entity)),
            category = profile.category,
            categoryLabel = profile.label,
            capacity = profile.capacity,
            fuel = current,
            rate = profile.refuelRate,
        },
        maxAmount = maxAmount,
        minAmount = Config.Refuel.MinAmount,
        fuels = fuels,
        defaultFuel = defaultFuel,
        payment = {
            methods = paymentMethods(),
            balances = balances,
            default = Config.Payment.Methods[Config.Payment.DefaultMethod] and Config.Payment.DefaultMethod or paymentMethods()[1],
        },
    })
end)

---------------------------------------------------------------------------------------------------
-- Zahájení tankování
---------------------------------------------------------------------------------------------------
local function releasePending(source, netId)
    if Refuel.byPlayer[source] == 'pending' then Refuel.byPlayer[source] = nil end
    if netId and Refuel.byVehicle[netId] == 'pending' then Refuel.byVehicle[netId] = nil end
end

Core.RegisterCallback('startRefuel', function(source, payload)
    if type(payload) ~= 'table' then return Core.Fail('error_invalid_data') end
    if not Core.Throttle(source, 'startRefuel', 1000) then return Core.Fail('error_too_fast') end
    if Refuel.byPlayer[source] then return Core.Fail('error_already_refueling') end

    local station = Stations.Get(payload.stationId)
    if not station then return Core.Fail('error_invalid_station') end
    if not station.open then return Core.Fail('error_station_closed') end

    local pumpCoords, pumpEntry = resolvePump(station, payload.pump)
    if not pumpCoords then
        Core.Suspicious(source, 'neplatný stojan při tankování')
        return Core.Fail('error_invalid_pump')
    end

    local entity, netId = getVehicleEntity(payload.netId)
    if not entity then return Core.Fail('error_no_vehicle') end
    if Refuel.byVehicle[netId] then return Core.Fail('error_vehicle_busy') end

    local method = payload.method
    if type(method) ~= 'string' or not Config.Payment.Methods[method] then return Core.Fail('error_invalid_payment') end

    local fuelType = payload.fuelType
    local fuel = type(fuelType) == 'string' and Config.FuelTypes[fuelType]
    if not fuel then return Core.Fail('error_invalid_fuel') end
    local allowed = false
    for _, ft in ipairs(fuelsForPump(station, pumpEntry)) do
        if ft == fuelType then allowed = true break end
    end
    if not allowed then return Core.Fail('error_fuel_not_sold') end

    local positionError = validatePosition(source, station, pumpCoords, entity)
    if positionError then return Core.Fail(positionError) end

    local profile = Fuel.GetProfile(entity, payload.class)
    if not profile then return Core.Fail('error_no_fuel_vehicle') end
    if not profile.fuelSet[fuelType] then return Core.Fail('error_fuel_incompatible', fuel.label) end

    -- rezervace hráče a vozidla ještě před prvním yieldem
    Refuel.byPlayer[source] = 'pending'
    Refuel.byVehicle[netId] = 'pending'

    local current = Fuel.Init(entity)
    if not current or not DoesEntityExist(entity) then
        releasePending(source, netId)
        return Core.Fail('error_no_vehicle')
    end

    -- po yieldu znovu ověřit stav (stanice mohla být zavřena, hráč mohl odejít)
    if not station.open then releasePending(source, netId) return Core.Fail('error_station_closed') end
    positionError = validatePosition(source, station, pumpCoords, entity)
    if positionError then releasePending(source, netId) return Core.Fail(positionError) end

    local maxAmount = Utils.Floor(profile.capacity * (100 - current) / 100, 2)
    if maxAmount < Config.Refuel.MinAmount then
        releasePending(source, netId)
        return Core.Fail('error_tank_full')
    end

    local amount
    if payload.full == true then
        amount = maxAmount
    else
        amount = Utils.ToNumber(payload.amount)
        if not amount then releasePending(source, netId) return Core.Fail('error_invalid_amount') end
        amount = Utils.Floor(amount, 2)
        if amount < Config.Refuel.MinAmount then
            releasePending(source, netId)
            return Core.Fail('error_min_amount', Config.Refuel.MinAmount)
        end
        amount = math.min(amount, maxAmount)
    end

    local unlimited = Stations.HasUnlimitedStock(station)
    if not unlimited then
        local available = Utils.Floor(station.stock[fuelType] or 0, 2)
        if available < Config.Refuel.MinAmount then
            releasePending(source, netId)
            return Core.Fail('error_out_of_stock', fuel.label)
        end
        amount = math.min(amount, available)
    end

    local price = Stations.GetPrice(station, fuelType)
    local total = math.ceil(amount * price - 1e-9)
    if total <= 0 then total = 1 end

    -- ověření a odečtení zálohy (bez yieldu mezi kontrolou a odečtením)
    local balance = Bridge.GetMoney(source, method)
    if balance < total then
        releasePending(source, netId)
        return Core.Fail('error_insufficient_funds', Utils.FormatMoney(total))
    end
    if not Bridge.RemoveMoney(source, method, total, 'xenon_fuel_refuel') then
        releasePending(source, netId)
        return Core.Fail('error_insufficient_funds', Utils.FormatMoney(total))
    end

    -- rezervace zásob
    if not unlimited then
        station.stock[fuelType] = station.stock[fuelType] - amount
    end

    nextSessionId = nextSessionId + 1
    local session = {
        id = nextSessionId,
        source = source,
        identifier = Bridge.GetIdentifier(source),
        playerName = Bridge.GetName(source),
        stationId = station.id,
        pumpCoords = pumpCoords,
        entity = entity,
        netId = netId,
        plate = Utils.TrimPlate(GetVehicleNumberPlateText(entity)),
        fuelType = fuelType,
        price = price,
        amount = amount,
        paid = total,
        method = method,
        startFuel = current,
        capacity = profile.capacity,
        rate = profile.refuelRate,
        reserved = not unlimited,
        delivered = 0,
        lastSetFuel = current,
        startedAt = GetGameTimer(),
        finished = false,
    }

    Refuel.sessions[session.id] = session
    Refuel.byPlayer[source] = session.id
    Refuel.byVehicle[netId] = session.id
    Fuel.SetFuelType(entity, fuelType)
    Refuel.StartLoop()

    Utils.Debug(('Tankování #%d: %s, %.2f %s %s, záloha %d'):format(session.id, session.playerName, amount, fuel.unit, fuelType, total))

    return Core.Success({
        id = session.id,
        amount = amount,
        price = price,
        total = total,
        rate = session.rate,
        startFuel = current,
        capacity = session.capacity,
        duration = amount / session.rate,
        fuel = { id = fuelType, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit },
        method = method,
    })
end)

---------------------------------------------------------------------------------------------------
-- Ukončení a vyúčtování
---------------------------------------------------------------------------------------------------
function Refuel.Finish(session, reason)
    if session.finished then return end
    session.finished = true

    Refuel.sessions[session.id] = nil
    if Refuel.byPlayer[session.source] == session.id then Refuel.byPlayer[session.source] = nil end
    if Refuel.byVehicle[session.netId] == session.id then Refuel.byVehicle[session.netId] = nil end

    local station = Stations.Get(session.stationId)
    local delivered
    if reason == 'completed' then
        delivered = session.amount
    else
        local elapsed = (GetGameTimer() - session.startedAt) / 1000
        delivered = math.min(session.amount, session.delivered, elapsed * session.rate)
    end
    delivered = Utils.Floor(math.max(0, delivered), 2)

    local cost
    if delivered >= session.amount then
        cost = session.paid
    else
        cost = math.min(session.paid, math.ceil(delivered * session.price - 1e-9))
    end
    if delivered <= 0 then cost = 0 end
    local refund = session.paid - cost

    -- konečný stav paliva vozidla
    if DoesEntityExist(session.entity) then
        Fuel.Set(session.entity, session.startFuel + delivered / session.capacity * 100)
    end

    -- vrácení nevyčerpané zálohy
    if refund > 0 then
        local refunded
        if session.dropped then
            refunded = Bridge.AddMoney(session.source, Config.Payment.RefundOnDisconnectAccount, refund, 'xenon_fuel_refuel_refund')
            if not refunded then Bridge.AddOfflineBank(session.identifier, refund) end
        else
            refunded = Bridge.AddMoney(session.source, session.method, refund, 'xenon_fuel_refuel_refund')
            if not refunded then Bridge.AddOfflineBank(session.identifier, refund) end
        end
    end

    -- vrácení nevyčerpané rezervace zásob
    if station and session.reserved then
        local capacity = station.cfg.capacity[session.fuelType] or math.huge
        station.stock[session.fuelType] = math.min(capacity, (station.stock[session.fuelType] or 0) + (session.amount - delivered))
    end

    local receipt
    if station and cost > 0 then
        local label = Stations.GetLabel(station)
        local fuel = Config.FuelTypes[session.fuelType]
        local now = os.time()

        station.stats.customers = station.stats.customers + 1
        station.stats.liters = station.stats.liters + delivered
        station.stats.revenue = station.stats.revenue + cost

        if Stations.IsOwned(station) then
            Stations.Credit(station, cost, 'sale', session.identifier, session.playerName,
                ('%s %s %s'):format(Utils.FormatNumber(delivered, 2), fuel.unit, fuel.label))
        else
            Stations.Save(station)
        end

        receipt = {
            number = Transactions.ReceiptNumber(),
            station = label,
            date = os.date('%d.%m.%Y', now),
            time = os.date('%H:%M:%S', now),
            fuel = fuel.label,
            fuelShort = fuel.short,
            color = fuel.color,
            unit = fuel.unit,
            liters = delivered,
            price = session.price,
            total = cost,
            method = session.method,
            plate = session.plate,
        }

        Transactions.LogRefuel({
            receipt = receipt.number,
            identifier = session.identifier,
            playerName = session.playerName,
            stationId = station.id,
            stationLabel = label,
            plate = session.plate,
            fuelType = session.fuelType,
            liters = delivered,
            price = session.price,
            total = cost,
            method = session.method,
            time = now,
        })

        if Config.Features.Receipts and not session.dropped and hasReceiptItem() then
            local metadata = {
                label = L('receipt_item_label', label),
                description = L('receipt_item_description',
                    receipt.date .. ' ' .. receipt.time,
                    Utils.FormatNumber(delivered, 2), fuel.unit, fuel.label,
                    Utils.FormatMoney(session.price, 2), Utils.FormatMoney(cost),
                    L('payment_' .. session.method), receipt.number),
                receipt = receipt,
            }
            local canCarry = exports.ox_inventory:CanCarryItem(session.source, 'fuel_receipt', 1, metadata)
            if canCarry then
                exports.ox_inventory:AddItem(session.source, 'fuel_receipt', 1, metadata)
            end
        end
    elseif station and session.reserved then
        Stations.Save(station)
    end

    if not session.dropped then
        TriggerClientEvent('xenon_fuel:client:refuelEnded', session.source, {
            id = session.id,
            reason = reason,
            liters = delivered,
            total = cost,
            refund = refund,
            receipt = receipt,
        })
    end

    Utils.Debug(('Tankování #%d ukončeno (%s): %.2f l, cena %d, vráceno %d'):format(session.id, reason, delivered, cost, refund))
end

Core.RegisterNetEvent('stopRefuel', function(source)
    local id = Refuel.byPlayer[source]
    local session = id and Refuel.sessions[id]
    if session then Refuel.Finish(session, 'stopped') end
end)

---------------------------------------------------------------------------------------------------
-- Průběh tankování (běží jen pokud existuje aktivní relace)
---------------------------------------------------------------------------------------------------
local function tick()
    local now = GetGameTimer()
    for _, session in pairs(Refuel.sessions) do
        local reason
        local elapsed = (now - session.startedAt) / 1000
        local delivered = math.min(session.amount, elapsed * session.rate)

        if not DoesEntityExist(session.entity) then
            reason = 'vehicle_gone'
        else
            local ped = GetPlayerPed(session.source)
            if not ped or ped == 0 then
                reason = 'player_gone'
            else
                local playerCoords = GetEntityCoords(ped)
                local vehicleCoords = GetEntityCoords(session.entity)
                if #(playerCoords - session.pumpCoords) > Config.Refuel.HoseLength + 1.0 then
                    reason = 'too_far'
                elseif #(vehicleCoords - session.pumpCoords) > Config.Refuel.MaxVehiclePumpDistance + 1.5
                    or #GetEntityVelocity(session.entity) > 1.5 then
                    reason = 'vehicle_moved'
                elseif GetVehiclePedIsIn(ped, false) ~= 0 then
                    reason = 'entered_vehicle'
                elseif GetIsVehicleEngineRunning(session.entity) then
                    reason = 'engine_started'
                end
            end
        end

        session.delivered = delivered

        if reason then
            Refuel.Finish(session, reason)
        elseif delivered >= session.amount then
            Refuel.Finish(session, 'completed')
        else
            local fuel = session.startFuel + delivered / session.capacity * 100
            if fuel - session.lastSetFuel >= 0.2 then
                session.lastSetFuel = fuel
                Fuel.Set(session.entity, fuel)
            end
        end
    end
end

function Refuel.StartLoop()
    if loopRunning then return end
    loopRunning = true
    CreateThread(function()
        while next(Refuel.sessions) do
            Wait(Config.Refuel.ServerTick)
            local ok, err = pcall(tick)
            if not ok then print(('^1[xenon_fuel] Chyba v průběhu tankování: %s^7'):format(tostring(err))) end
        end
        loopRunning = false
    end)
end

--- Ukončí všechny relace (vypnutí resource) – vrátí zálohy
function Refuel.FinishAll(reason)
    for _, session in pairs(Refuel.sessions) do
        Refuel.Finish(session, reason or 'stopped')
    end
end

---------------------------------------------------------------------------------------------------
-- Historie tankování hráče
---------------------------------------------------------------------------------------------------
Core.RegisterCallback('getHistory', function(source)
    if not Config.Features.RefuelHistory then return Core.Fail('error_feature_disabled') end
    if not Core.Throttle(source, 'history', 2000) then return Core.Fail('error_too_fast') end
    local rows = Transactions.GetPlayerHistory(Bridge.GetIdentifier(source), Config.History.PlayerLimit)
    return Core.Success(rows)
end)

---------------------------------------------------------------------------------------------------
-- Odpojení hráče během tankování
---------------------------------------------------------------------------------------------------
local function onDrop(source)
    local id = Refuel.byPlayer[source]
    local session = type(id) == 'number' and Refuel.sessions[id]
    if session then
        session.dropped = true
        Refuel.Finish(session, 'disconnected')
    end
    if Refuel.byPlayer[source] == 'pending' then Refuel.byPlayer[source] = nil end
end

Bridge.OnPlayerDropped(onDrop)
AddEventHandler('playerDropped', function()
    onDrop(source)
end)
