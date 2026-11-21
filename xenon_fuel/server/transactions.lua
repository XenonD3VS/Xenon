--[[
    xenon_fuel – historie transakcí, tankování a finanční přehledy
]]

Transactions = {}

local receiptCounter = 0

--- Unikátní číslo účtenky, např. XF-LZ4K2A-07
function Transactions.ReceiptNumber()
    receiptCounter = (receiptCounter + 1) % 1296
    local chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    local function base36(n, len)
        local out = ''
        repeat
            local d = n % 36
            out = chars:sub(d + 1, d + 1) .. out
            n = n // 36
        until n == 0
        while #out < len do out = '0' .. out end
        return out
    end
    return ('XF-%s-%s%s'):format(base36(os.time(), 6), base36(receiptCounter, 2), base36(math.random(0, 35), 1))
end

--- Zápis finančního pohybu benzinky
function Transactions.LogFinance(stationId, txType, amount, balance, actor, actorName, note)
    MySQL.insert(
        'INSERT INTO `xenon_fuel_finance` (station_id, type, amount, balance, actor, actor_name, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        { stationId, txType, math.floor(amount), math.floor(balance), actor, actorName, note and note:sub(1, 255) or nil, os.time() }
    )
end

--- Zápis tankování (historie hráče i prodejů benzinky)
function Transactions.LogRefuel(data)
    MySQL.insert(
        'INSERT INTO `xenon_fuel_refuels` (receipt, identifier, player_name, station_id, station_label, plate, fuel_type, liters, price_per_liter, total, payment_method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        {
            data.receipt, data.identifier, data.playerName, data.stationId, data.stationLabel, data.plate,
            data.fuelType, data.liters, data.price, data.total, data.method, data.time or os.time(),
        }
    )
end

function Transactions.GetPlayerHistory(identifier, limit)
    return MySQL.query.await(
        'SELECT receipt, station_label, plate, fuel_type, liters, price_per_liter, total, payment_method, created_at FROM `xenon_fuel_refuels` WHERE identifier = ? ORDER BY id DESC LIMIT ?',
        { identifier, limit or Config.History.PlayerLimit }
    ) or {}
end

function Transactions.GetStationSales(stationId, page, pageSize)
    pageSize = pageSize or Config.History.StationPageSize
    page = math.max(1, math.floor(page or 1))
    local rows = MySQL.query.await(
        'SELECT receipt, player_name, plate, fuel_type, liters, price_per_liter, total, payment_method, created_at FROM `xenon_fuel_refuels` WHERE station_id = ? ORDER BY id DESC LIMIT ? OFFSET ?',
        { stationId, pageSize, (page - 1) * pageSize }
    ) or {}
    local total = MySQL.scalar.await('SELECT COUNT(*) FROM `xenon_fuel_refuels` WHERE station_id = ?', { stationId }) or 0
    return { rows = rows, page = page, pages = math.max(1, math.ceil(total / pageSize)), total = total }
end

function Transactions.GetStationFinance(stationId, page, pageSize)
    pageSize = pageSize or Config.History.StationPageSize
    page = math.max(1, math.floor(page or 1))
    local rows = MySQL.query.await(
        'SELECT type, amount, balance, actor_name, note, created_at FROM `xenon_fuel_finance` WHERE station_id = ? ORDER BY id DESC LIMIT ? OFFSET ?',
        { stationId, pageSize, (page - 1) * pageSize }
    ) or {}
    local total = MySQL.scalar.await('SELECT COUNT(*) FROM `xenon_fuel_finance` WHERE station_id = ?', { stationId }) or 0
    return { rows = rows, page = page, pages = math.max(1, math.ceil(total / pageSize)), total = total }
end

--- Souhrn příjmů a nákladů podle typu (od koupě benzinky)
function Transactions.GetFinanceSummary(stationId, since)
    local rows = MySQL.query.await(
        'SELECT type, SUM(amount) AS total, COUNT(*) AS count FROM `xenon_fuel_finance` WHERE station_id = ? AND created_at >= ? GROUP BY type',
        { stationId, since or 0 }
    ) or {}
    local summary = { income = 0, expenses = 0, byType = {} }
    for _, row in ipairs(rows) do
        local total = tonumber(row.total) or 0
        summary.byType[row.type] = { total = total, count = tonumber(row.count) or 0 }
        if row.type == 'sale' then
            summary.income = summary.income + total
        elseif row.type == 'order' or row.type == 'order_refund' or row.type == 'salary' then
            summary.expenses = summary.expenses - total
        end
    end
    summary.profit = summary.income - summary.expenses
    return summary
end

local function timezoneOffset()
    local now = os.time()
    return os.difftime(now, os.time(os.date('!*t', now)))
end

--- Tržby a náklady po dnech (graf v přehledu)
function Transactions.GetChart(stationId, days, since)
    days = days or Config.History.ChartDays
    local offset = math.floor(timezoneOffset())
    local today = (os.time() + offset) // 86400
    local from = math.max((today - days + 1) * 86400 - offset, since or 0)

    local rows = MySQL.query.await([[
        SELECT FLOOR((created_at + ?) / 86400) AS day,
               SUM(CASE WHEN type = 'sale' THEN amount ELSE 0 END) AS revenue,
               SUM(CASE WHEN type IN ('order', 'order_refund', 'salary') THEN -amount ELSE 0 END) AS costs
        FROM `xenon_fuel_finance`
        WHERE station_id = ? AND created_at >= ?
        GROUP BY day
    ]], { offset, stationId, from }) or {}

    local byDay = {}
    for _, row in ipairs(rows) do
        byDay[math.floor(tonumber(row.day) or 0)] = row
    end

    local result = {}
    for i = days - 1, 0, -1 do
        local day = today - i
        local row = byDay[day]
        result[#result + 1] = {
            date = day * 86400 - offset + 43200,
            revenue = row and math.floor(tonumber(row.revenue) or 0) or 0,
            costs = row and math.max(0, math.floor(tonumber(row.costs) or 0)) or 0,
        }
    end
    return result
end

--- Odpracovaný čas zaměstnanců za posledních 7 dní (z uzavřených směn)
function Transactions.GetWeeklyHours(stationId)
    local rows = MySQL.query.await(
        'SELECT identifier, SUM(seconds) AS seconds FROM `xenon_fuel_shifts` WHERE station_id = ? AND started_at >= ? GROUP BY identifier',
        { stationId, os.time() - 7 * 86400 }
    ) or {}
    local result = {}
    for _, row in ipairs(rows) do
        result[row.identifier] = tonumber(row.seconds) or 0
    end
    return result
end

function Transactions.LogShift(stationId, identifier, startedAt, endedAt, seconds, earned)
    if seconds <= 0 then return end
    MySQL.insert(
        'INSERT INTO `xenon_fuel_shifts` (station_id, identifier, started_at, ended_at, seconds, earned) VALUES (?, ?, ?, ?, ?, ?)',
        { stationId, identifier, startedAt, endedAt, math.floor(seconds), math.floor(earned or 0) }
    )
end
