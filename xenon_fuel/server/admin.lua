--[[
    xenon_fuel – admin panel (server)
    Každá akce ověřuje admin oprávnění (ESX skupina nebo ACE), má rate limit a zapisuje se
    do audit logu (tabulka xenon_fuel_admin_log + konzole).
]]

Admin = {}

---------------------------------------------------------------------------------------------------
-- Audit log
---------------------------------------------------------------------------------------------------
function Admin.Audit(source, action, target, details)
    local identifier = source ~= 0 and Bridge.GetIdentifier(source) or 'console'
    local name = source ~= 0 and Bridge.GetName(source) or 'Console'
    details = details and tostring(details):sub(1, 255) or nil
    MySQL.insert(
        'INSERT INTO `xenon_fuel_admin_log` (admin, admin_name, action, target, details, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        { identifier, name, action, target and tostring(target):sub(1, 100) or nil, details, os.time() }
    )
    print(('^3[xenon_fuel] Admin %s (%s): %s %s %s^7'):format(name, identifier, action, tostring(target or ''), details or ''))
end

---------------------------------------------------------------------------------------------------
-- Sestavení dat panelu
---------------------------------------------------------------------------------------------------
local function timezoneOffset()
    local now = os.time()
    return math.floor(os.difftime(now, os.time(os.date('!*t', now))))
end

--- Tržby všech benzinek (veřejných i vlastněných) po dnech z historie tankování
local function globalChart(days)
    local offset = timezoneOffset()
    local today = (os.time() + offset) // 86400
    local from = (today - days + 1) * 86400 - offset
    local rows = MySQL.query.await([[
        SELECT FLOOR((created_at + ?) / 86400) AS day, SUM(total) AS revenue, SUM(liters) AS liters, COUNT(*) AS refuels
        FROM `xenon_fuel_refuels` WHERE created_at >= ? GROUP BY day
    ]], { offset, from }) or {}
    local byDay = {}
    for _, row in ipairs(rows) do byDay[math.floor(tonumber(row.day) or 0)] = row end
    local result = {}
    for i = days - 1, 0, -1 do
        local day = today - i
        local row = byDay[day]
        result[#result + 1] = {
            date = day * 86400 - offset + 43200,
            revenue = row and math.floor(tonumber(row.revenue) or 0) or 0,
            liters = row and Utils.Round(tonumber(row.liters) or 0, 1) or 0,
            refuels = row and math.floor(tonumber(row.refuels) or 0) or 0,
        }
    end
    return result
end

local function stockPercent(station)
    local stock, capacity = 0, 0
    for _, ft in ipairs(station.cfg.fuelTypes) do
        stock = stock + (station.stock[ft] or 0)
        capacity = capacity + (station.cfg.capacity[ft] or 0)
    end
    return capacity > 0 and Utils.Round(stock / capacity * 100, 1) or 0
end

local function buildOverview()
    local total, owned, closed, balances, revenue, customers, liters = 0, 0, 0, 0, 0, 0, 0
    local top = {}
    for _, id in ipairs(Utils.StationIds) do
        local station = Stations.Get(id)
        total = total + 1
        if Stations.IsOwned(station) then
            owned = owned + 1
            balances = balances + station.balance
        end
        if not station.open then closed = closed + 1 end
        revenue = revenue + station.stats.revenue
        customers = customers + station.stats.customers
        liters = liters + station.stats.liters
        top[#top + 1] = { id = id, label = Stations.GetLabel(station), revenue = station.stats.revenue, owned = Stations.IsOwned(station) }
    end
    table.sort(top, function(a, b) return a.revenue > b.revenue end)
    for i = #top, 6, -1 do top[i] = nil end

    local onDuty, jobs, pendingOrders = 0, 0, 0
    for _ in pairs(Employees.onDuty) do onDuty = onDuty + 1 end
    for _ in pairs(Deliveries.jobs) do jobs = jobs + 1 end
    for _, order in pairs(Deliveries.orders) do if order.id then pendingOrders = pendingOrders + 1 end end

    return {
        stations = total, owned = owned, closed = closed,
        balances = balances, revenue = revenue, customers = customers, liters = Utils.Round(liters, 1),
        sessions = Utils.TableCount(Refuel.sessions), orders = pendingOrders, jobs = jobs, onDuty = onDuty,
        players = #Bridge.GetPlayers(),
        chart = globalChart(Config.History.ChartDays),
        top = top,
    }
end

local function buildStations()
    local list = {}
    for _, id in ipairs(Utils.StationIds) do
        local station = Stations.Get(id)
        local fuels = {}
        for _, ft in ipairs(station.cfg.fuelTypes) do
            local fuel = Config.FuelTypes[ft]
            fuels[#fuels + 1] = {
                id = ft, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit,
                stock = Utils.Round(station.stock[ft] or 0, 1), capacity = station.cfg.capacity[ft],
                price = Stations.GetPrice(station, ft), defaultPrice = station.cfg.prices[ft],
            }
        end
        list[#list + 1] = {
            id = id,
            label = Stations.GetLabel(station),
            defaultLabel = station.cfg.label,
            typeLabel = station.cfg.typeLabel,
            owned = Stations.IsOwned(station),
            ownerName = station.ownerName,
            balance = station.balance,
            open = station.open,
            revenue = station.stats.revenue,
            customers = station.stats.customers,
            liters = Utils.Round(station.stats.liters, 1),
            stockPct = stockPercent(station),
            unlimited = Stations.HasUnlimitedStock(station),
            employees = Utils.TableCount(Employees.byStation[id] or {}),
            orders = Deliveries.CountActive(id),
            purchasable = station.cfg.purchasable,
            price = station.cfg.price,
            customPrices = next(station.prices) ~= nil,
            fuels = fuels,
        }
    end
    return list
end

local function buildPlayers()
    local list = {}
    for _, source in ipairs(Bridge.GetPlayers()) do
        list[#list + 1] = { id = source, name = Bridge.GetName(source) }
    end
    table.sort(list, function(a, b) return a.id < b.id end)
    return list
end

local function buildOrders()
    local list = {}
    for _, order in pairs(Deliveries.orders) do
        if order.id then
            local station = Stations.Get(order.stationId)
            list[#list + 1] = {
                id = order.id, stationId = order.stationId, station = station and Stations.GetLabel(station) or order.stationId,
                fuelType = order.fuelType, liters = order.liters, cost = order.cost, method = order.method,
                status = order.status, driverName = order.driverName, orderedByName = order.orderedByName,
                createdAt = order.createdAt, deliverAt = order.deliverAt,
            }
        end
    end
    table.sort(list, function(a, b) return a.id > b.id end)
    return list
end

local function buildLive()
    local now = GetGameTimer()
    local sessions, jobs, duty = {}, {}, {}
    for _, s in pairs(Refuel.sessions) do
        local station = Stations.Get(s.stationId)
        sessions[#sessions + 1] = {
            id = s.id, player = s.playerName, source = s.source,
            station = station and Stations.GetLabel(station) or s.stationId,
            plate = s.plate, fuelType = s.fuelType, amount = s.amount,
            delivered = Utils.Round(math.min(s.amount, (now - s.startedAt) / 1000 * s.rate), 2),
            paid = s.paid, method = s.method,
        }
    end
    for source, job in pairs(Deliveries.jobs) do
        local order = Deliveries.orders[job.orderId]
        local station = order and Stations.Get(order.stationId)
        jobs[#jobs + 1] = {
            source = source, driver = Bridge.GetName(source), orderId = job.orderId, status = job.status,
            station = station and Stations.GetLabel(station) or '—', liters = job.liters, reward = job.reward,
            minutes = math.floor((os.time() - job.startedAt) / 60),
        }
    end
    for source, shift in pairs(Employees.onDuty) do
        local station = Stations.Get(shift.stationId)
        local employee = Employees.Get(shift.stationId, shift.identifier)
        duty[#duty + 1] = {
            source = source, name = employee and employee.name or Bridge.GetName(source),
            station = station and Stations.GetLabel(station) or shift.stationId,
            rank = employee and Utils.Ranks[employee.rank] and Utils.Ranks[employee.rank].label or '',
            seconds = math.floor(shift.seconds), earned = shift.earned,
        }
    end
    table.sort(sessions, function(a, b) return a.id < b.id end)
    table.sort(jobs, function(a, b) return a.orderId < b.orderId end)
    table.sort(duty, function(a, b) return a.name < b.name end)
    return { sessions = sessions, jobs = jobs, duty = duty }
end

local function buildLogs()
    return MySQL.query.await(
        'SELECT admin_name, action, target, details, created_at FROM `xenon_fuel_admin_log` ORDER BY id DESC LIMIT ?',
        { Config.Admin.LogLimit }
    ) or {}
end

local ALL_SECTIONS = { 'overview', 'stations', 'players', 'orders', 'live', 'logs' }

function Admin.Build(source, sections)
    local wanted = {}
    for _, s in ipairs(sections or ALL_SECTIONS) do wanted[s] = true end
    local data = {}
    if wanted.overview then data.overview = buildOverview() end
    if wanted.stations then data.stations = buildStations() end
    if wanted.players then data.players = buildPlayers() end
    if wanted.orders then data.orders = buildOrders() end
    if wanted.live then data.live = buildLive() end
    if wanted.logs then data.logs = buildLogs() end
    if not sections then
        data.admin = { name = Bridge.GetName(source), areaMax = Config.Admin.AreaRefuelMaxRadius }
    end
    return data
end

Core.RegisterCallback('adminOpen', function(source)
    if not Bridge.IsAdmin(source) then
        Core.Suspicious(source, 'pokus o otevření admin panelu bez oprávnění')
        return Core.Fail('error_no_permission')
    end
    if not Core.Throttle(source, 'adminOpen', 1000) then return Core.Fail('error_too_fast') end
    return Core.Success(Admin.Build(source))
end)

---------------------------------------------------------------------------------------------------
-- Akce
---------------------------------------------------------------------------------------------------
local function getStation(payload)
    local station = Stations.Get(payload.stationId)
    if not station then return nil, Core.Fail('error_invalid_station') end
    return station
end

local function findNearestVehicle(source, maxDistance)
    local coords = Core.GetPlayerCoords(source)
    if not coords then return nil end
    local best, bestDist
    for _, vehicle in ipairs(GetAllVehicles()) do
        local dist = #(GetEntityCoords(vehicle) - coords)
        if dist <= maxDistance and (not bestDist or dist < bestDist) then
            best, bestDist = vehicle, dist
        end
    end
    return best
end

local Actions = {}

Actions.refresh = { sections = ALL_SECTIONS, run = function() return Core.Success() end }

Actions.teleport = {
    sections = {},
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        local c = station.cfg.coords
        SetEntityCoords(GetPlayerPed(source), c.x, c.y, c.z + 0.5, false, false, false, false)
        Admin.Audit(source, 'teleport', station.id)
        local result = Core.Success(nil, 'admin_teleported', Stations.GetLabel(station))
        result.closed = true
        return result
    end,
}

Actions.toggleStation = {
    sections = { 'stations', 'overview' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        station.open = not station.open
        Stations.Save(station)
        Stations.Publish(station)
        Admin.Audit(source, 'toggle_station', station.id, station.open and 'open' or 'closed')
        return Core.Success(nil, station.open and 'station_opened' or 'station_closed')
    end,
}

Actions.setBalance = {
    sections = { 'stations', 'overview' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        if not Stations.IsOwned(station) then return Core.Fail('error_not_owned') end
        local balance = Utils.ToInt(payload.balance)
        if not balance or balance < 0 or balance > Config.Security.MaxTransactionAmount then return Core.Fail('error_invalid_amount') end
        local diff = balance - station.balance
        if diff == 0 then return Core.Success() end
        station.balance = balance
        Stations.Save(station)
        Transactions.LogFinance(station.id, 'admin', diff, balance, Bridge.GetIdentifier(source), Bridge.GetName(source), L('finance_note_admin'))
        Admin.Audit(source, 'set_balance', station.id, ('%d -> %d'):format(balance - diff, balance))
        return Core.Success(nil, 'admin_balance_set', Stations.GetLabel(station), Utils.FormatMoney(balance))
    end,
}

Actions.setStock = {
    sections = { 'stations' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        local ft = payload.fuelType
        if type(ft) ~= 'string' or not station.cfg.fuelSet[ft] then return Core.Fail('error_invalid_fuel') end
        local liters = Utils.ToNumber(payload.liters)
        if not liters then return Core.Fail('error_invalid_amount') end
        liters = Utils.Round(Utils.Clamp(liters, 0, station.cfg.capacity[ft]), 2)
        station.stock[ft] = liters
        Stations.Save(station)
        Admin.Audit(source, 'set_stock', station.id, ('%s = %s'):format(ft, liters))
        return Core.Success(nil, 'admin_stock_set', Config.FuelTypes[ft].label, Utils.FormatNumber(liters))
    end,
}

Actions.fillStock = {
    sections = { 'stations' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        for _, ft in ipairs(station.cfg.fuelTypes) do station.stock[ft] = station.cfg.capacity[ft] end
        Stations.Save(station)
        Admin.Audit(source, 'fill_stock', station.id)
        return Core.Success(nil, 'admin_stock_filled', Stations.GetLabel(station))
    end,
}

Actions.resetPrices = {
    sections = { 'stations' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        station.prices = {}
        Stations.Save(station)
        Stations.Publish(station)
        Admin.Audit(source, 'reset_prices', station.id)
        return Core.Success(nil, 'admin_prices_reset', Stations.GetLabel(station))
    end,
}

Actions.rename = {
    sections = { 'stations', 'overview' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        local clean = Utils.SanitizeText(payload.label or '', 96)
        if clean == nil then return Core.Fail('error_invalid_data') end
        if clean ~= '' then
            local len = Utils.Utf8Len(clean)
            if len < Config.Ownership.RenameLength.min or len > Config.Ownership.RenameLength.max then
                return Core.Fail('error_rename_length', Config.Ownership.RenameLength.min, Config.Ownership.RenameLength.max)
            end
        end
        station.customLabel = clean ~= '' and clean or nil
        Stations.Save(station)
        Stations.Publish(station)
        Admin.Audit(source, 'rename', station.id, Stations.GetLabel(station))
        return Core.Success(nil, 'station_renamed', Stations.GetLabel(station))
    end,
}

Actions.transfer = {
    sections = { 'stations', 'overview' },
    run = function(source, payload)
        if not Config.Features.Ownership then return Core.Fail('error_feature_disabled') end
        local station, err = getStation(payload)
        if not station then return err end
        local target = Utils.ToInt(payload.target)
        local identifier = target and Bridge.GetIdentifier(target)
        if not identifier then return Core.Fail('error_player_not_found') end
        if station.owner == identifier then return Core.Fail('error_already_owner') end

        local previous = station.owner
        if Employees.Get(station.id, identifier) then
            Employees.Remove(station.id, identifier, 'transfer') -- yield (DB)
        end
        station.owner = identifier
        station.ownerName = Bridge.GetName(target)
        if not previous then
            station.purchasePrice = 0
            station.purchasedAt = os.time()
            station.balance = 0
            station.stats = { revenue = 0, costs = 0, customers = 0, liters = 0 }
        end
        Stations.Save(station)
        Stations.Publish(station)
        Transactions.LogFinance(station.id, 'admin', 0, station.balance, Bridge.GetIdentifier(source), Bridge.GetName(source),
            L('finance_note_transfer', station.ownerName))
        if previous then Employees.PushAccess(previous, station.id) end
        Employees.PushAccess(identifier, station.id)
        Core.Notify(target, L('admin_transfer_received', Stations.GetLabel(station)), 'success')
        Admin.Audit(source, 'transfer', station.id, ('%s -> %s'):format(previous or 'public', identifier))
        return Core.Success(nil, 'admin_transferred', Stations.GetLabel(station), station.ownerName)
    end,
}

Actions.resetStation = {
    sections = { 'stations', 'overview', 'orders' },
    run = function(source, payload)
        local station, err = getStation(payload)
        if not station then return err end
        if payload.confirm ~= station.id then return Core.Fail('error_invalid_data') end
        local label = station.cfg.label
        Ownership.Reset(station)
        Admin.Audit(source, 'reset_station', station.id)
        return Core.Success(nil, 'cmd_reset_done', label)
    end,
}

Actions.deliverOrder = {
    sections = { 'orders', 'stations', 'overview', 'live' },
    run = function(source, payload)
        local id = Utils.ToInt(payload.orderId)
        local order = id and Deliveries.orders[id]
        if not order then return Core.Fail('error_order_not_found') end
        local delivered = Deliveries.ForceDeliver(order)
        Admin.Audit(source, 'deliver_order', id, ('%s %s'):format(order.fuelType, delivered))
        return Core.Success(nil, 'admin_order_delivered', id)
    end,
}

Actions.cancelOrder = {
    sections = { 'orders', 'stations', 'overview', 'live' },
    run = function(source, payload)
        local id = Utils.ToInt(payload.orderId)
        local order = id and Deliveries.orders[id]
        if not order then return Core.Fail('error_order_not_found') end
        Deliveries.ForceCancel(order, Bridge.GetIdentifier(source), Bridge.GetName(source))
        Admin.Audit(source, 'cancel_order', id)
        return Core.Success(nil, 'order_cancelled', id)
    end,
}

Actions.stopSession = {
    sections = { 'live', 'overview' },
    run = function(source, payload)
        local id = Utils.ToInt(payload.sessionId)
        local session = id and Refuel.sessions[id]
        if not session then return Core.Fail('error_session_not_found') end
        Refuel.Finish(session, 'admin')
        Admin.Audit(source, 'stop_refuel', session.playerName, session.plate)
        return Core.Success(nil, 'admin_session_stopped', session.playerName)
    end,
}

Actions.cancelJob = {
    sections = { 'live', 'orders', 'overview' },
    run = function(source, payload)
        local target = Utils.ToInt(payload.source)
        if not target or not Deliveries.jobs[target] then return Core.Fail('error_no_job') end
        local name = Bridge.GetName(target)
        Deliveries.EndJob(target, 'admin')
        Admin.Audit(source, 'cancel_job', name)
        return Core.Success(nil, 'admin_job_cancelled', name)
    end,
}

Actions.clockOut = {
    sections = { 'live', 'overview' },
    run = function(source, payload)
        local target = Utils.ToInt(payload.source)
        if not target or not Employees.onDuty[target] then return Core.Fail('error_not_on_duty') end
        local name = Bridge.GetName(target)
        Employees.ClockOut(target)
        Core.Notify(target, L('admin_clocked_out_target'), 'warning')
        Admin.Audit(source, 'clock_out', name)
        return Core.Success(nil, 'admin_clocked_out', name)
    end,
}

Actions.vehicleFuel = {
    sections = {},
    run = function(source, payload)
        local amount = Utils.ToNumber(payload.amount)
        if not amount then return Core.Fail('error_invalid_amount') end
        amount = Utils.Clamp(amount, 0, 100)
        local vehicle
        if payload.target == 'nearest' then
            vehicle = findNearestVehicle(source, 10.0)
        else
            local v = GetVehiclePedIsIn(GetPlayerPed(source), false)
            vehicle = v ~= 0 and v or nil
        end
        if not vehicle then return Core.Fail(payload.target == 'nearest' and 'error_no_vehicle_near' or 'error_not_in_vehicle') end
        Fuel.Set(vehicle, amount)
        local plate = Utils.TrimPlate(GetVehicleNumberPlateText(vehicle))
        Admin.Audit(source, 'set_fuel', plate, amount)
        return Core.Success({ plate = plate, fuel = amount }, 'admin_vehicle_fuel', plate, Utils.FormatNumber(amount))
    end,
}

Actions.areaRefuel = {
    sections = {},
    run = function(source, payload)
        local radius = Utils.ToNumber(payload.radius)
        if not radius or radius <= 0 then return Core.Fail('error_invalid_amount') end
        radius = math.min(radius, Config.Admin.AreaRefuelMaxRadius)
        local coords = Core.GetPlayerCoords(source)
        if not coords then return Core.Fail('error_no_player') end
        local count = 0
        for _, vehicle in ipairs(GetAllVehicles()) do
            if #(GetEntityCoords(vehicle) - coords) <= radius and Fuel.GetProfile(vehicle) then
                Fuel.Set(vehicle, 100)
                count = count + 1
            end
        end
        Admin.Audit(source, 'area_refuel', ('%dm'):format(math.floor(radius)), count)
        return Core.Success({ count = count }, 'admin_area_refuel', count, math.floor(radius))
    end,
}

Actions.plateLookup = {
    sections = {},
    run = function(_, payload)
        local plate = Utils.TrimPlate(payload.plate)
        if plate == '' or #plate > 8 then return Core.Fail('error_invalid_plate') end
        local fuel = Fuel.GetPlateFuel(plate)
        return Core.Success({ plate = plate, fuel = fuel })
    end,
}

Actions.plateSet = {
    sections = {},
    run = function(source, payload)
        local plate = Utils.TrimPlate(payload.plate)
        if plate == '' or #plate > 8 then return Core.Fail('error_invalid_plate') end
        local amount = Utils.ToNumber(payload.amount)
        if not amount then return Core.Fail('error_invalid_amount') end
        amount = Utils.Clamp(amount, 0, 100)
        Fuel.SetPlateFuel(plate, amount)
        Admin.Audit(source, 'set_plate_fuel', plate, amount)
        return Core.Success({ plate = plate, fuel = amount }, 'admin_vehicle_fuel', plate, Utils.FormatNumber(amount))
    end,
}

local READ_ONLY = { refresh = true, plateLookup = true }

Core.RegisterCallback('adminAction', function(source, action, payload)
    if not Bridge.IsAdmin(source) then
        Core.Suspicious(source, ('admin akce %s bez oprávnění'):format(tostring(action)))
        return Core.Fail('error_no_permission')
    end
    local handler = type(action) == 'string' and Actions[action]
    if not handler then return Core.Fail('error_invalid_data') end
    if type(payload) ~= 'table' then payload = {} end
    if not Core.Throttle(source, READ_ONLY[action] and 'adminRead' or 'adminAction', READ_ONLY[action] and 300 or 500) then
        return Core.Fail('error_too_fast')
    end

    local lockKey = 'admin:' .. source
    if not Core.Lock(lockKey) then return Core.Fail('error_too_fast') end
    local ok, result = pcall(handler.run, source, payload)
    Core.Unlock(lockKey)
    if not ok then
        print(('^1[xenon_fuel] Chyba v admin akci %s: %s^7'):format(action, tostring(result)))
        return Core.Fail('error_internal')
    end

    if result.ok and handler.sections and #handler.sections > 0 then
        local sections = { table.unpack(handler.sections) }
        if action ~= 'refresh' then sections[#sections + 1] = 'logs' end
        result.update = Admin.Build(source, sections)
    end
    return result
end)
