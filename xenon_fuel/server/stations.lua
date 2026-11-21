--[[
    xenon_fuel – stav čerpacích stanic (server)
    Paměť serveru je autoritativní, databáze se aktualizuje sériově (bez souběžných zápisů
    stejného řádku), takže nemůže dojít k přepsání novějšího stavu starším.
]]

Stations = { list = {} }

local function defaultState(cfg)
    local stock = {}
    for _, ft in ipairs(cfg.fuelTypes) do stock[ft] = 0 end
    return {
        id = cfg.id,
        cfg = cfg,
        owner = nil,
        ownerName = nil,
        customLabel = nil,
        balance = 0,
        open = true,
        prices = {},
        stock = stock,
        stats = { revenue = 0, costs = 0, customers = 0, liters = 0 },
        purchasePrice = 0,
        purchasedAt = nil,
        version = 0,
        savedVersion = 0,
        saving = false,
    }
end

function Stations.Get(id)
    if type(id) ~= 'string' then return nil end
    return Stations.list[id]
end

function Stations.GetLabel(station)
    return station.customLabel or station.cfg.label
end

function Stations.IsOwned(station)
    return Config.Features.Ownership and station.owner ~= nil
end

--- Neomezené zásoby (sklad vypnut nebo veřejná benzinka)
function Stations.HasUnlimitedStock(station)
    if not Config.Features.Stock then return true end
    return not Stations.IsOwned(station) and Config.Stock.PublicUnlimited
end

function Stations.GetPrice(station, fuelType)
    if Stations.IsOwned(station) and station.prices[fuelType] then
        return station.prices[fuelType]
    end
    return station.cfg.prices[fuelType]
end

function Stations.GetStock(station, fuelType)
    if Stations.HasUnlimitedStock(station) then return math.huge end
    return station.stock[fuelType] or 0
end

function Stations.GetOwnedCount(identifier)
    local count = 0
    for _, station in pairs(Stations.list) do
        if station.owner == identifier then count = count + 1 end
    end
    return count
end

function Stations.GetOwnedBy(identifier)
    local result = {}
    for id, station in pairs(Stations.list) do
        if station.owner == identifier then result[#result + 1] = id end
    end
    return result
end

---------------------------------------------------------------------------------------------------
-- Replikace veřejných údajů klientům (GlobalState – automaticky i pro nově připojené hráče)
---------------------------------------------------------------------------------------------------
function Stations.Publish(station)
    local prices = {}
    for _, ft in ipairs(station.cfg.fuelTypes) do
        prices[ft] = Stations.GetPrice(station, ft)
    end
    GlobalState['xenon_fuel:' .. station.id] = {
        label = Stations.GetLabel(station),
        open = station.open,
        owned = Stations.IsOwned(station),
        ownerName = station.ownerName,
        prices = prices,
    }
end

---------------------------------------------------------------------------------------------------
-- Ukládání
---------------------------------------------------------------------------------------------------
local function persist(station, async)
    local query = async and MySQL.query or MySQL.query.await
    local pricesJson = next(station.prices) and json.encode(station.prices) or nil
    query([[
        INSERT INTO `xenon_fuel_stations`
            (id, owner, owner_name, label, balance, is_open, prices, total_revenue, total_costs, customers, liters_sold, purchase_price, purchased_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            owner = VALUES(owner), owner_name = VALUES(owner_name), label = VALUES(label), balance = VALUES(balance),
            is_open = VALUES(is_open), prices = VALUES(prices), total_revenue = VALUES(total_revenue),
            total_costs = VALUES(total_costs), customers = VALUES(customers), liters_sold = VALUES(liters_sold),
            purchase_price = VALUES(purchase_price), purchased_at = VALUES(purchased_at)
    ]], {
        station.id, station.owner, station.ownerName, station.customLabel, math.floor(station.balance),
        station.open and 1 or 0, pricesJson, math.floor(station.stats.revenue), math.floor(station.stats.costs),
        station.stats.customers, Utils.Round(station.stats.liters, 2), station.purchasePrice, station.purchasedAt,
    })

    local values, params = {}, {}
    for ft, liters in pairs(station.stock) do
        values[#values + 1] = '(?, ?, ?)'
        params[#params + 1] = station.id
        params[#params + 1] = ft
        params[#params + 1] = Utils.Round(liters, 2)
    end
    if #values > 0 then
        query(
            ('INSERT INTO `xenon_fuel_stock` (station_id, fuel_type, liters) VALUES %s ON DUPLICATE KEY UPDATE liters = VALUES(liters)')
                :format(table.concat(values, ',')),
            params
        )
    end
end

--- Naplánuje uložení benzinky. Zápisy jedné benzinky běží vždy postupně a uloží se poslední stav.
function Stations.Save(station)
    station.version = station.version + 1
    if station.saving then return end
    station.saving = true
    CreateThread(function()
        while station.savedVersion ~= station.version do
            local version = station.version
            local ok, err = pcall(persist, station)
            if not ok then
                print(('^1[xenon_fuel] Nepodařilo se uložit benzinku %s: %s^7'):format(station.id, tostring(err)))
                Wait(5000)
            else
                station.savedVersion = version
            end
        end
        station.saving = false
    end)
end

--- Okamžité uložení všech neuložených benzinek (vypnutí serveru / resource)
---@param async boolean při zastavení resource nelze čekat na výsledek
function Stations.SaveAllPending(async)
    for _, station in pairs(Stations.list) do
        if station.savedVersion ~= station.version then
            local ok = pcall(persist, station, async)
            if ok then station.savedVersion = station.version end
        end
    end
end

---------------------------------------------------------------------------------------------------
-- Firemní účet – všechny změny zůstatku procházejí těmito funkcemi
---------------------------------------------------------------------------------------------------

--- Připíše částku na firemní účet
function Stations.Credit(station, amount, txType, actor, actorName, note)
    amount = math.floor(amount)
    if amount <= 0 then return false end
    station.balance = station.balance + amount
    Stations.Save(station)
    Transactions.LogFinance(station.id, txType, amount, station.balance, actor, actorName, note)
    return true
end

--- Odečte částku z firemního účtu, pokud je dostatek prostředků (atomicky – bez přerušení)
function Stations.Debit(station, amount, txType, actor, actorName, note, isCost)
    amount = math.floor(amount)
    if amount <= 0 or station.balance < amount then return false end
    station.balance = station.balance - amount
    if isCost then station.stats.costs = station.stats.costs + amount end
    Stations.Save(station)
    Transactions.LogFinance(station.id, txType, -amount, station.balance, actor, actorName, note)
    return true
end

--- Obnoví benzinku do výchozího (nevlastněného) stavu
function Stations.Reset(station)
    local cfg = station.cfg
    local fresh = defaultState(cfg)
    station.owner = nil
    station.ownerName = nil
    station.customLabel = nil
    station.balance = 0
    station.open = true
    station.prices = {}
    station.stock = fresh.stock
    station.stats = fresh.stats
    station.purchasePrice = 0
    station.purchasedAt = nil
    Stations.Save(station)
    Stations.Publish(station)
end

---------------------------------------------------------------------------------------------------
-- Načtení
---------------------------------------------------------------------------------------------------
function Stations.Load()
    for id, cfg in pairs(Utils.Stations) do
        Stations.list[id] = defaultState(cfg)
    end

    local rows = MySQL.query.await('SELECT * FROM `xenon_fuel_stations`') or {}
    for _, row in ipairs(rows) do
        local station = Stations.list[row.id]
        if station then
            station.owner = row.owner
            station.ownerName = row.owner_name
            station.customLabel = row.label
            station.balance = math.floor(tonumber(row.balance) or 0)
            station.open = row.is_open == 1 or row.is_open == true
            station.stats.revenue = tonumber(row.total_revenue) or 0
            station.stats.costs = tonumber(row.total_costs) or 0
            station.stats.customers = tonumber(row.customers) or 0
            station.stats.liters = tonumber(row.liters_sold) or 0
            station.purchasePrice = tonumber(row.purchase_price) or 0
            station.purchasedAt = tonumber(row.purchased_at)

            if row.prices then
                local ok, prices = pcall(json.decode, row.prices)
                if ok and type(prices) == 'table' then
                    for ft, price in pairs(prices) do
                        local fuel = Config.FuelTypes[ft]
                        price = Utils.ToNumber(price)
                        if fuel and station.cfg.fuelSet[ft] and price then
                            station.prices[ft] = Utils.Clamp(price, fuel.minPrice, fuel.maxPrice)
                        end
                    end
                end
            end
        elseif row.owner then
            print(('^3[xenon_fuel] V databázi je vlastněná benzinka "%s", která není v configu.^7'):format(row.id))
        end
    end

    local stockRows = MySQL.query.await('SELECT * FROM `xenon_fuel_stock`') or {}
    for _, row in ipairs(stockRows) do
        local station = Stations.list[row.station_id]
        if station and station.cfg.fuelSet[row.fuel_type] then
            station.stock[row.fuel_type] = Utils.Clamp(tonumber(row.liters) or 0, 0, station.cfg.capacity[row.fuel_type])
        end
    end

    for _, station in pairs(Stations.list) do
        Stations.Publish(station)
    end

    print(('^2[xenon_fuel]^7 Načteno %d benzinek'):format(Utils.TableCount(Stations.list)))
end

exports('GetStationOwner', function(stationId)
    local station = Stations.Get(stationId)
    return station and station.owner or nil
end)

exports('GetStationPrice', function(stationId, fuelType)
    local station = Stations.Get(stationId)
    return station and Stations.GetPrice(station, fuelType) or nil
end)
