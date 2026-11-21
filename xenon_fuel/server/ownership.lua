--[[
    xenon_fuel – vlastnictví benzinek (nákup, prodej, přejmenování, reset)
]]

Ownership = {}

local function sellValue(station)
    return math.floor((station.purchasePrice or 0) * Config.Ownership.SellBackPercent)
end
Ownership.SellValue = sellValue

--- Informace pro nákupní okno
Core.RegisterCallback('getPurchaseInfo', function(source, stationId)
    if not Config.Features.Ownership then return Core.Fail('error_feature_disabled') end
    local station = Stations.Get(stationId)
    if not station then return Core.Fail('error_invalid_station') end
    if not station.cfg.purchasable then return Core.Fail('error_not_purchasable') end
    if station.owner then return Core.Fail('error_already_owned') end

    local identifier = Bridge.GetIdentifier(source)
    local fuels = {}
    for _, ft in ipairs(station.cfg.fuelTypes) do
        local fuel = Config.FuelTypes[ft]
        fuels[#fuels + 1] = {
            id = ft, label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit,
            capacity = station.cfg.capacity[ft], price = station.cfg.prices[ft],
        }
    end

    local accounts = {}
    for method, enabled in pairs(Config.Ownership.PurchaseAccounts) do
        if enabled then accounts[method] = Bridge.GetMoney(source, method) end
    end

    return Core.Success({
        id = station.id,
        label = station.cfg.label,
        typeLabel = station.cfg.typeLabel,
        price = station.cfg.price,
        fuels = fuels,
        pumps = type(station.cfg.pumps) == 'table' and #station.cfg.pumps or nil,
        startingStock = Config.Ownership.StartingStock,
        owned = Stations.GetOwnedCount(identifier),
        maxOwned = Config.Ownership.MaxStationsPerPlayer,
        accounts = accounts,
        sellBack = Config.Ownership.SellBackPercent,
    })
end)

Core.RegisterCallback('buyStation', function(source, stationId, method)
    if not Config.Features.Ownership then return Core.Fail('error_feature_disabled') end
    if not Core.Throttle(source, 'buyStation', 2000) then return Core.Fail('error_too_fast') end

    local station = Stations.Get(stationId)
    if not station then return Core.Fail('error_invalid_station') end
    if not station.cfg.purchasable then return Core.Fail('error_not_purchasable') end
    if station.owner then return Core.Fail('error_already_owned') end
    if type(method) ~= 'string' or not Config.Ownership.PurchaseAccounts[method] then
        return Core.Fail('error_invalid_payment')
    end

    local dist = Core.PlayerDistance(source, station.cfg.coords)
    if not dist or dist > station.cfg.radius + 25.0 then return Core.Fail('error_not_at_station') end

    local identifier = Bridge.GetIdentifier(source)
    if Stations.GetOwnedCount(identifier) >= Config.Ownership.MaxStationsPerPlayer then
        return Core.Fail('error_max_owned', Config.Ownership.MaxStationsPerPlayer)
    end

    local price = station.cfg.price
    if Bridge.GetMoney(source, method) < price then
        return Core.Fail('error_insufficient_funds', Utils.FormatMoney(price))
    end

    -- odečtení peněz a převod vlastnictví proběhne bez přerušení (žádný yield mezi kontrolou a zápisem)
    if not Bridge.RemoveMoney(source, method, price, 'xenon_fuel_station_purchase') then
        return Core.Fail('error_insufficient_funds', Utils.FormatMoney(price))
    end

    local name = Bridge.GetName(source)
    station.owner = identifier
    station.ownerName = name
    station.customLabel = nil
    station.balance = 0
    station.open = true
    station.prices = {}
    station.stats = { revenue = 0, costs = 0, customers = 0, liters = 0 }
    station.purchasePrice = price
    station.purchasedAt = os.time()
    for _, ft in ipairs(station.cfg.fuelTypes) do
        station.stock[ft] = Config.Features.Stock and math.floor(station.cfg.capacity[ft] * Config.Ownership.StartingStock) or 0
    end

    Stations.Save(station)
    Stations.Publish(station)
    Transactions.LogFinance(station.id, 'purchase', 0, 0, identifier, name, L('finance_note_purchase', Utils.FormatMoney(price)))
    Employees.PushAccess(identifier, station.id)

    print(('^2[xenon_fuel]^7 %s (%s) koupil benzinku %s za %s'):format(name, identifier, station.id, price))
    return Core.Success({ id = station.id }, 'station_bought', station.cfg.label, Utils.FormatMoney(price))
end)

--- Prodej benzinky státu (pouze vlastník)
function Ownership.Sell(source, station)
    local identifier = Bridge.GetIdentifier(source)
    if station.owner ~= identifier then return Core.Fail('error_no_permission') end

    local lockKey = 'station_sell:' .. station.id
    if not Core.Lock(lockKey) then return Core.Fail('error_too_fast') end

    Employees.RemoveAll(station.id) -- obsahuje databázové operace (yield)

    -- po přerušení znovu ověřit, že benzinku stále vlastní
    if station.owner ~= identifier then
        Core.Unlock(lockKey)
        return Core.Fail('error_no_permission')
    end

    -- Zrušení aktivních objednávek (vrácení peněz na firemní účet)
    Deliveries.CancelStationOrders(station, identifier, Bridge.GetName(source))

    local payout = sellValue(station) + math.max(0, station.balance)
    local label = Stations.GetLabel(station)

    Stations.Reset(station)
    Core.Unlock(lockKey)
    Transactions.LogFinance(station.id, 'sale_station', 0, 0, identifier, Bridge.GetName(source), L('finance_note_sold', Utils.FormatMoney(payout)))

    Bridge.AddMoney(source, Config.Ownership.PayoutAccount == 'cash' and 'cash' or 'bank', payout, 'xenon_fuel_station_sale')
    Employees.PushAccess(identifier, station.id)

    print(('^3[xenon_fuel]^7 %s prodal benzinku %s za %s'):format(identifier, station.id, payout))
    return Core.Success({ sold = true }, 'station_sold', label, Utils.FormatMoney(payout))
end

function Ownership.Rename(source, station, label)
    if station.owner ~= Bridge.GetIdentifier(source) then return Core.Fail('error_no_permission') end
    if not Config.Ownership.AllowRename then return Core.Fail('error_feature_disabled') end

    local clean = Utils.SanitizeText(label, 96)
    if clean == nil then return Core.Fail('error_invalid_data') end
    if clean == '' then
        station.customLabel = nil
    else
        local len = Utils.Utf8Len(clean)
        if len < Config.Ownership.RenameLength.min or len > Config.Ownership.RenameLength.max then
            return Core.Fail('error_rename_length', Config.Ownership.RenameLength.min, Config.Ownership.RenameLength.max)
        end
        station.customLabel = clean
    end
    Stations.Save(station)
    Stations.Publish(station)
    return Core.Success(nil, 'station_renamed', Stations.GetLabel(station))
end

--- Admin reset (bez náhrady)
function Ownership.Reset(station)
    local owner = station.owner
    Deliveries.CancelStationOrders(station, nil, 'Admin')
    Employees.RemoveAll(station.id)
    Stations.Reset(station)
    if owner then Employees.PushAccess(owner, station.id) end
end
