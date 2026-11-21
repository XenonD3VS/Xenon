--[[
    xenon_fuel – management panel benzinky
    Každá akce ověřuje oprávnění, polohu hráče a data na serveru.
]]

Management = {}

local function rankInfo(rankId)
    local rank = Utils.Ranks[rankId]
    return rank and rank.label or rankId, rank and rank.grade or 0, rank and rank.salary or 0
end

local function isNearStation(source, station, extra)
    local coords = Core.GetPlayerCoords(source)
    if not coords then return false end
    if #(coords - station.cfg.coords) <= station.cfg.radius + (extra or 30.0) then return true end
    local mgmt = station.cfg.management
    return mgmt ~= nil and #(coords - vector3(mgmt.x, mgmt.y, mgmt.z)) <= 6.0
end

--- Přístupová data pro klienta (zobrazení možností v ox_target, blipy)
function Management.BuildAccess(source, station)
    if not station then return nil end
    local identifier = Bridge.GetIdentifier(source)
    local access = Employees.GetAccess(station, identifier)
    local shift = Employees.GetShift(source)
    local hasAnyPerm = false
    if access then
        for _, value in pairs(access.perms) do
            if value then hasAnyPerm = true break end
        end
    end
    return {
        stationId = station.id,
        owned = Stations.IsOwned(station),
        purchasable = Config.Features.Ownership and station.cfg.purchasable and not station.owner,
        price = station.cfg.price,
        isOwner = access and access.isOwner or false,
        isEmployee = access and access.isEmployee or false,
        canManage = access ~= nil and (access.isOwner or hasAnyPerm or access.isEmployee),
        onDuty = shift ~= nil and shift.stationId == station.id,
    }
end

Core.RegisterCallback('getAccess', function(source, stationId)
    if not Core.Throttle(source, 'getAccess:' .. tostring(stationId), 500) then return nil end
    return Management.BuildAccess(source, Stations.Get(stationId))
end)

--- Přístup ke všem benzinkám najednou (blipy po připojení)
Core.RegisterCallback('getAllAccess', function(source)
    if not Core.Throttle(source, 'getAllAccess', 5000) then return nil end
    local identifier = Bridge.GetIdentifier(source)
    local result = {}
    for id, station in pairs(Stations.list) do
        if station.owner == identifier or Employees.Get(id, identifier) then
            result[id] = Management.BuildAccess(source, station)
        end
    end
    return result
end)

---------------------------------------------------------------------------------------------------
-- Sestavení dat panelu
---------------------------------------------------------------------------------------------------
local ALL_SECTIONS = { 'station', 'viewer', 'stats', 'fuels', 'orders', 'employees', 'finance', 'sales', 'chart' }

function Management.Build(source, station, access, sections)
    local wanted = {}
    for _, s in ipairs(sections or ALL_SECTIONS) do wanted[s] = true end
    local perms = access.perms
    local data = {}

    if wanted.station then
        data.station = {
            id = station.id,
            label = Stations.GetLabel(station),
            defaultLabel = station.cfg.label,
            typeLabel = station.cfg.typeLabel,
            open = station.open,
            ownerName = station.ownerName,
            purchasePrice = station.purchasePrice,
            purchasedAt = station.purchasedAt,
            sellValue = Ownership.SellValue(station),
            balance = (perms.view_finances or perms.withdraw or perms.deposit) and station.balance or nil,
            canRename = access.isOwner and Config.Ownership.AllowRename,
            renameLength = Config.Ownership.RenameLength,
            pumps = type(station.cfg.pumps) == 'table' and #station.cfg.pumps or nil,
        }
    end

    if wanted.viewer then
        local shift = Employees.GetShift(source)
        local rankLabel = access.rank and rankInfo(access.rank) or nil
        data.viewer = {
            name = Bridge.GetName(source),
            isOwner = access.isOwner,
            isEmployee = access.isEmployee,
            rank = access.rank,
            rankLabel = rankLabel,
            grade = access.grade,
            perms = perms,
            onDuty = shift ~= nil and shift.stationId == station.id,
            shiftSeconds = shift and shift.stationId == station.id and shift.seconds or 0,
            shiftEarned = shift and shift.stationId == station.id and shift.earned or 0,
            features = {
                stock = Config.Features.Stock,
                orders = Config.Features.Orders,
                tanker = Config.Features.TankerJob and Config.Orders.Methods.tanker.enabled,
                employees = Config.Features.Employees,
                payroll = Config.Features.Payroll,
            },
        }
    end

    if wanted.stats and perms.view_overview then
        data.stats = {
            revenue = station.stats.revenue,
            costs = station.stats.costs,
            profit = station.stats.revenue - station.stats.costs,
            customers = station.stats.customers,
            liters = Utils.Round(station.stats.liters, 2),
            employees = Utils.TableCount(Employees.byStation[station.id] or {}),
            activeOrders = Deliveries.CountActive(station.id),
        }
    end

    if wanted.fuels and (perms.view_overview or perms.view_stock or perms.manage_prices) then
        local fuels = {}
        for _, ft in ipairs(station.cfg.fuelTypes) do
            local fuel = Config.FuelTypes[ft]
            fuels[#fuels + 1] = {
                id = ft, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit,
                price = Stations.GetPrice(station, ft),
                defaultPrice = station.cfg.prices[ft],
                minPrice = fuel.minPrice, maxPrice = fuel.maxPrice,
                wholesale = fuel.wholesale,
                stock = (perms.view_stock or perms.view_overview) and Utils.Round(station.stock[ft] or 0, 2) or nil,
                capacity = station.cfg.capacity[ft],
                pending = perms.view_stock and Deliveries.PendingLiters(station.id, ft) or nil,
            }
        end
        data.fuels = fuels
    end

    if wanted.orders and perms.view_stock and Config.Features.Orders then
        data.orders = Deliveries.GetStationOrders(station.id)
        data.orderConfig = {
            min = Config.Orders.MinLiters,
            max = Config.Orders.MaxLiters,
            maxPending = Config.Orders.MaxPendingPerStation,
            supplier = Config.Orders.Methods.supplier.enabled and {
                fee = Config.Orders.Methods.supplier.feePerLiter,
                delay = Config.Orders.Methods.supplier.delayMinutes,
            } or nil,
            tanker = (Config.Features.TankerJob and Config.Orders.Methods.tanker.enabled) and {
                reward = Config.Orders.Methods.tanker.reward,
                fallback = Config.Orders.Methods.tanker.fallbackToSupplierAfter,
            } or nil,
        }
    end

    if wanted.employees and Config.Features.Employees then
        local list = {}
        local weekly = Transactions.GetWeeklyHours(station.id)
        local myIdentifier = Bridge.GetIdentifier(source)
        for identifier, employee in pairs(Employees.byStation[station.id] or {}) do
            if perms.manage_employees or identifier == myIdentifier then
                local label, grade, salary = rankInfo(employee.rank)
                local target = Bridge.GetSourceFromIdentifier(identifier)
                local shift = target and Employees.GetShift(target)
                local onShift = shift ~= nil and shift.stationId == station.id
                list[#list + 1] = {
                    identifier = identifier,
                    name = employee.name,
                    rank = employee.rank,
                    rankLabel = label,
                    grade = grade,
                    salary = salary,
                    overrides = employee.overrides,
                    perms = Employees.GetEffectivePermissions(employee),
                    secondsWorked = math.floor(employee.secondsWorked),
                    weekSeconds = math.floor((weekly[identifier] or 0) + (onShift and shift.seconds or 0)),
                    totalPaid = employee.totalPaid,
                    hiredAt = employee.hiredAt,
                    lastShift = employee.lastShift,
                    online = target ~= nil,
                    onDuty = onShift,
                    manageable = identifier ~= myIdentifier and (access.isOwner or grade < access.grade),
                    isMe = identifier == myIdentifier,
                }
            end
        end
        table.sort(list, function(a, b)
            if a.grade ~= b.grade then return a.grade > b.grade end
            return a.name < b.name
        end)
        data.employees = list
        data.ranks = Config.Employees.Ranks
        data.permissionList = Config.Permissions
        data.maxEmployees = Config.Employees.MaxPerStation
    end

    if wanted.finance and perms.view_finances then
        data.finance = Transactions.GetStationFinance(station.id, 1)
        data.financeSummary = Transactions.GetFinanceSummary(station.id, station.purchasedAt or 0)
    end

    if wanted.sales and perms.view_transactions then
        data.sales = Transactions.GetStationSales(station.id, 1)
    end

    if wanted.chart and perms.view_overview then
        data.chart = Transactions.GetChart(station.id, Config.History.ChartDays, station.purchasedAt)
    end

    return data
end

local function getAccessChecked(source, stationId)
    local station = Stations.Get(stationId)
    if not station then return nil, nil, 'error_invalid_station' end
    if not Stations.IsOwned(station) then return nil, nil, 'error_not_owned' end
    local access = Employees.GetAccess(station, Bridge.GetIdentifier(source))
    if not access then return nil, nil, 'error_no_permission' end
    if not isNearStation(source, station) then return nil, nil, 'error_not_at_station' end
    return station, access
end

Core.RegisterCallback('openManagement', function(source, stationId)
    if not Config.Features.Ownership then return Core.Fail('error_feature_disabled') end
    if not Core.Throttle(source, 'openManagement', 1000) then return Core.Fail('error_too_fast') end
    local station, access, err = getAccessChecked(source, stationId)
    if not station then return Core.Fail(err) end
    return Core.Success(Management.Build(source, station, access))
end)

---------------------------------------------------------------------------------------------------
-- Akce
---------------------------------------------------------------------------------------------------
local function money(value)
    value = Utils.ToInt(value)
    if not value or value <= 0 or value > Config.Security.MaxTransactionAmount then return nil end
    return value
end

local Actions = {}

Actions.setPrice = {
    perm = 'manage_prices',
    sections = { 'fuels' },
    run = function(source, station, access, payload)
        local ft = payload.fuelType
        local fuel = type(ft) == 'string' and Config.FuelTypes[ft]
        if not fuel or not station.cfg.fuelSet[ft] then return Core.Fail('error_invalid_fuel') end
        local price = Utils.ToNumber(payload.price)
        if not price then return Core.Fail('error_invalid_price') end
        price = Utils.Round(price, 2)
        if price < fuel.minPrice or price > fuel.maxPrice then
            return Core.Fail('error_price_range', Utils.FormatMoney(fuel.minPrice, 2), Utils.FormatMoney(fuel.maxPrice, 2))
        end
        station.prices[ft] = price
        Stations.Save(station)
        Stations.Publish(station)
        return Core.Success(nil, 'price_set', fuel.label, Utils.FormatMoney(price, 2))
    end,
}

Actions.toggleOpen = {
    perm = 'toggle_station',
    sections = { 'station' },
    run = function(_, station)
        station.open = not station.open
        Stations.Save(station)
        Stations.Publish(station)
        return Core.Success(nil, station.open and 'station_opened' or 'station_closed')
    end,
}

Actions.rename = {
    owner = true,
    sections = { 'station' },
    run = function(source, station, _, payload)
        return Ownership.Rename(source, station, payload.label)
    end,
}

Actions.orderFuel = {
    perm = 'order_fuel',
    sections = { 'station', 'stats', 'fuels', 'orders', 'finance', 'chart' },
    run = function(source, station, _, payload)
        return Deliveries.CreateOrder(source, station, payload.fuelType, payload.liters, payload.method)
    end,
}

Actions.cancelOrder = {
    perm = 'cancel_orders',
    sections = { 'station', 'stats', 'fuels', 'orders', 'finance', 'chart' },
    run = function(source, station, _, payload)
        return Deliveries.CancelOrder(source, station, payload.orderId)
    end,
}

Actions.nearbyPlayers = {
    perm = 'manage_employees',
    sections = {},
    run = function(source, station)
        local myCoords = Core.GetPlayerCoords(source)
        local list = {}
        if myCoords then
            for _, target in ipairs(Bridge.GetPlayers()) do
                if target ~= source then
                    local coords = Core.GetPlayerCoords(target)
                    local identifier = Bridge.GetIdentifier(target)
                    if coords and #(coords - myCoords) <= Config.Employees.HireDistance
                        and identifier ~= station.owner and not Employees.Get(station.id, identifier) then
                        list[#list + 1] = { id = target, name = Bridge.GetName(target) }
                    end
                end
            end
        end
        return Core.Success(list)
    end,
}

Actions.hire = {
    perm = 'manage_employees',
    sections = {},
    run = function(source, station, access, payload)
        if not Config.Features.Employees then return Core.Fail('error_feature_disabled') end
        return Employees.CreateOffer(source, station, access, payload.target, payload.rank)
    end,
}

Actions.fire = {
    perm = 'manage_employees',
    sections = { 'employees', 'stats' },
    run = function(source, station, access, payload)
        return Employees.Fire(source, station, access, payload.identifier)
    end,
}

Actions.setRank = {
    perm = 'manage_employees',
    sections = { 'employees' },
    run = function(source, station, access, payload)
        return Employees.SetRank(source, station, access, payload.identifier, payload.rank)
    end,
}

Actions.setPermissions = {
    perm = 'manage_employees',
    sections = { 'employees' },
    run = function(source, station, access, payload)
        return Employees.SetPermissions(source, station, access, payload.identifier, payload.permissions)
    end,
}

Actions.deposit = {
    perm = 'deposit',
    sections = { 'station', 'finance' },
    run = function(source, station, _, payload)
        local amount = money(payload.amount)
        if not amount then return Core.Fail('error_invalid_amount') end
        local method = payload.method
        if method ~= 'cash' and method ~= 'bank' then return Core.Fail('error_invalid_payment') end
        if not Bridge.RemoveMoney(source, method, amount, 'xenon_fuel_company_deposit') then
            return Core.Fail('error_insufficient_funds', Utils.FormatMoney(amount))
        end
        Stations.Credit(station, amount, 'deposit', Bridge.GetIdentifier(source), Bridge.GetName(source), L('payment_' .. method))
        return Core.Success(nil, 'deposit_done', Utils.FormatMoney(amount))
    end,
}

Actions.withdraw = {
    perm = 'withdraw',
    sections = { 'station', 'finance' },
    run = function(source, station, _, payload)
        local amount = money(payload.amount)
        if not amount then return Core.Fail('error_invalid_amount') end
        local method = payload.method
        if method ~= 'cash' and method ~= 'bank' then return Core.Fail('error_invalid_payment') end
        if not Stations.Debit(station, amount, 'withdraw', Bridge.GetIdentifier(source), Bridge.GetName(source), L('payment_' .. method), false) then
            return Core.Fail('error_company_funds', Utils.FormatMoney(amount))
        end
        if not Bridge.AddMoney(source, method, amount, 'xenon_fuel_company_withdraw') then
            -- hráč není dostupný – vrácení na firemní účet
            Stations.Credit(station, amount, 'deposit', nil, 'System', 'rollback')
            return Core.Fail('error_internal')
        end
        return Core.Success(nil, 'withdraw_done', Utils.FormatMoney(amount))
    end,
}

Actions.sell = {
    owner = true,
    sections = {},
    run = function(source, station, _, payload)
        if payload.confirm ~= station.id then return Core.Fail('error_invalid_data') end
        return Ownership.Sell(source, station)
    end,
}

Actions.duty = {
    employee = true,
    sections = { 'viewer', 'employees' },
    run = function(source, station)
        local shift = Employees.GetShift(source)
        if shift and shift.stationId == station.id then
            return Employees.ClockOut(source)
        elseif shift then
            return Core.Fail('error_on_duty_elsewhere')
        end
        return Employees.ClockIn(source, station)
    end,
}

Actions.quit = {
    employee = true,
    sections = {},
    run = function(source, station)
        return Employees.Quit(source, station)
    end,
}

Actions.salesPage = {
    perm = 'view_transactions',
    sections = {},
    run = function(_, station, _, payload)
        return Core.Success(Transactions.GetStationSales(station.id, Utils.ToInt(payload.page) or 1))
    end,
}

Actions.financePage = {
    perm = 'view_finances',
    sections = {},
    run = function(_, station, _, payload)
        return Core.Success(Transactions.GetStationFinance(station.id, Utils.ToInt(payload.page) or 1))
    end,
}

Actions.refresh = {
    sections = nil, -- vše
    run = function() return Core.Success() end,
}

Core.RegisterCallback('mgmtAction', function(source, stationId, action, payload)
    local handler = type(action) == 'string' and Actions[action]
    if not handler then return Core.Fail('error_invalid_data') end
    if type(payload) ~= 'table' then payload = {} end

    local light = action == 'salesPage' or action == 'financePage' or action == 'nearbyPlayers'
    if not Core.Throttle(source, light and 'mgmtRead' or 'mgmtAction', light and 300 or Config.Security.ActionCooldown) then
        return Core.Fail('error_too_fast')
    end

    local station, access, err = getAccessChecked(source, stationId)
    if not station then return Core.Fail(err) end

    if handler.owner and not access.isOwner then return Core.Fail('error_no_permission') end
    if handler.employee and not access.isEmployee then return Core.Fail('error_no_permission') end
    if handler.perm and access.perms[handler.perm] ~= true then
        Core.Suspicious(source, ('akce %s bez oprávnění %s'):format(action, handler.perm))
        return Core.Fail('error_no_permission')
    end

    local lockKey = 'mgmt:' .. source
    if not Core.Lock(lockKey) then return Core.Fail('error_too_fast') end
    local ok, result = pcall(handler.run, source, station, access, payload)
    Core.Unlock(lockKey)
    if not ok then
        print(('^1[xenon_fuel] Chyba v akci %s: %s^7'):format(action, tostring(result)))
        return Core.Fail('error_internal')
    end

    -- obnovení dat panelu (jen relevantní sekce), pokud má hráč stále přístup
    if result.ok and (handler.sections == nil or #handler.sections > 0) then
        local newAccess = Stations.IsOwned(station) and Employees.GetAccess(station, Bridge.GetIdentifier(source))
        if newAccess then
            local sections = handler.sections and { table.unpack(handler.sections) } or nil
            if sections then sections[#sections + 1] = 'viewer' end
            result.update = Management.Build(source, station, newAccess, sections)
        else
            result.closed = true
        end
    elseif result.ok and (action == 'sell' or action == 'quit') then
        result.closed = true
    end

    if result.ok and action ~= 'salesPage' and action ~= 'financePage' and action ~= 'nearbyPlayers' then
        Employees.PushAccess(Bridge.GetIdentifier(source), station.id)
    end
    return result
end)
