--[[
    xenon_fuel – zaměstnanci, oprávnění, směny a výplaty
]]

Employees = {
    byStation = {},     -- [stationId][identifier] = employee
    onDuty = {},        -- [source] = shift
    offers = {},        -- [targetSource] = offer
}

local ALL_PERMISSIONS = {}
for _, perm in ipairs(Config.Permissions) do ALL_PERMISSIONS[perm] = true end

local OWNER_GRADE = 1000

local function stationEmployees(stationId)
    local list = Employees.byStation[stationId]
    if not list then
        list = {}
        Employees.byStation[stationId] = list
    end
    return list
end

local function decodePermissions(raw)
    if not raw then return {} end
    local ok, data = pcall(json.decode, raw)
    if not ok or type(data) ~= 'table' then return {} end
    local result = {}
    for perm, value in pairs(data) do
        if ALL_PERMISSIONS[perm] and type(value) == 'boolean' then result[perm] = value end
    end
    return result
end

function Employees.Load()
    local rows = MySQL.query.await('SELECT * FROM `xenon_fuel_employees`') or {}
    local count = 0
    for _, row in ipairs(rows) do
        if Stations.Get(row.station_id) then
            local rank = Utils.Ranks[row.rank] and row.rank or Config.Employees.DefaultRank
            stationEmployees(row.station_id)[row.identifier] = {
                id = row.id,
                stationId = row.station_id,
                identifier = row.identifier,
                name = row.name,
                rank = rank,
                overrides = decodePermissions(row.permissions),
                secondsWorked = tonumber(row.seconds_worked) or 0,
                totalPaid = tonumber(row.total_paid) or 0,
                hiredAt = tonumber(row.hired_at) or os.time(),
                lastShift = tonumber(row.last_shift),
            }
            count = count + 1
        end
    end
    Utils.Debug(('Načteno %d zaměstnanců'):format(count))
end

function Employees.Get(stationId, identifier)
    local list = Employees.byStation[stationId]
    return list and list[identifier] or nil
end

function Employees.GetEffectivePermissions(employee)
    local rank = Utils.Ranks[employee.rank] or Utils.Ranks[Config.Employees.DefaultRank]
    local perms = {}
    for perm in pairs(ALL_PERMISSIONS) do
        local override = employee.overrides[perm]
        if override ~= nil then
            perms[perm] = override
        else
            perms[perm] = rank and rank.permissions[perm] == true or false
        end
    end
    return perms
end

--- Přístup hráče k benzince
---@return table|nil { isOwner, isEmployee, grade, rank, perms }
function Employees.GetAccess(station, identifier)
    if not identifier or not Config.Features.Ownership then return nil end
    if station.owner == identifier then
        return { isOwner = true, isEmployee = false, grade = OWNER_GRADE, rank = nil, perms = ALL_PERMISSIONS }
    end
    if not Config.Features.Employees or not station.owner then return nil end
    local employee = Employees.Get(station.id, identifier)
    if not employee then return nil end
    local rank = Utils.Ranks[employee.rank]
    return {
        isOwner = false,
        isEmployee = true,
        grade = rank and rank.grade or 0,
        rank = employee.rank,
        perms = Employees.GetEffectivePermissions(employee),
        employee = employee,
    }
end

function Employees.HasPermission(station, identifier, perm)
    local access = Employees.GetAccess(station, identifier)
    return access ~= nil and access.perms[perm] == true, access
end

--- Odešle hráči aktualizovaný přístup k benzince (pro zobrazení možností v ox_target)
function Employees.PushAccess(identifier, stationId)
    local source = Bridge.GetSourceFromIdentifier(identifier)
    if source then
        TriggerClientEvent('xenon_fuel:client:accessUpdate', source, stationId, Management.BuildAccess(source, Stations.Get(stationId)))
    end
end

local function saveEmployee(employee)
    MySQL.update(
        'UPDATE `xenon_fuel_employees` SET `rank` = ?, permissions = ?, seconds_worked = ?, total_paid = ?, last_shift = ?, name = ? WHERE id = ?',
        {
            employee.rank, next(employee.overrides) and json.encode(employee.overrides) or nil,
            math.floor(employee.secondsWorked), math.floor(employee.totalPaid), employee.lastShift, employee.name, employee.id,
        }
    )
end

---------------------------------------------------------------------------------------------------
-- Nábor
---------------------------------------------------------------------------------------------------
function Employees.CreateOffer(source, station, access, targetSource, rankId)
    targetSource = Utils.ToInt(targetSource)
    local rank = Utils.Ranks[rankId]
    if not rank then return Core.Fail('error_invalid_rank') end
    if not access.isOwner and rank.grade >= access.grade then return Core.Fail('error_rank_too_high') end
    if not targetSource or targetSource == source or not Bridge.GetPlayer(targetSource) then
        return Core.Fail('error_player_not_found')
    end

    local targetIdentifier = Bridge.GetIdentifier(targetSource)
    if targetIdentifier == station.owner then return Core.Fail('error_is_owner') end
    if Employees.Get(station.id, targetIdentifier) then return Core.Fail('error_already_employee') end
    if Utils.TableCount(stationEmployees(station.id)) >= Config.Employees.MaxPerStation then
        return Core.Fail('error_max_employees', Config.Employees.MaxPerStation)
    end

    local myCoords, targetCoords = Core.GetPlayerCoords(source), Core.GetPlayerCoords(targetSource)
    if not myCoords or not targetCoords or #(myCoords - targetCoords) > Config.Employees.HireDistance then
        return Core.Fail('error_player_too_far')
    end

    local existing = Employees.offers[targetSource]
    if existing and existing.expires > os.time() then return Core.Fail('error_offer_pending') end

    Employees.offers[targetSource] = {
        stationId = station.id,
        rank = rank.id,
        from = source,
        fromIdentifier = Bridge.GetIdentifier(source),
        expires = os.time() + Config.Employees.OfferTimeout,
    }

    TriggerClientEvent('xenon_fuel:client:jobOffer', targetSource, {
        station = Stations.GetLabel(station),
        rank = rank.label,
        salary = rank.salary,
        interval = Config.Payroll.Interval,
        from = Bridge.GetName(source),
        timeout = Config.Employees.OfferTimeout,
    })
    return Core.Success(nil, 'offer_sent', Bridge.GetName(targetSource))
end

Core.RegisterNetEvent('respondOffer', function(source, accepted)
    local offer = Employees.offers[source]
    Employees.offers[source] = nil
    if not offer then return end

    local station = Stations.Get(offer.stationId)
    local fromSource = Bridge.GetSourceFromIdentifier(offer.fromIdentifier)

    if offer.expires < os.time() then
        Core.Notify(source, L('offer_expired'), 'error')
        return
    end

    if accepted ~= true then
        if fromSource then Core.Notify(fromSource, L('offer_declined', Bridge.GetName(source)), 'error') end
        return
    end

    -- ověření, že se mezitím nic nezměnilo
    local identifier = Bridge.GetIdentifier(source)
    if not station or not station.owner or station.owner == identifier or Employees.Get(station.id, identifier) then
        Core.Notify(source, L('offer_invalid'), 'error')
        return
    end
    if Utils.TableCount(stationEmployees(station.id)) >= Config.Employees.MaxPerStation then
        Core.Notify(source, L('error_max_employees', Config.Employees.MaxPerStation), 'error')
        return
    end

    local name = Bridge.GetName(source)
    local now = os.time()
    local employee = {
        id = nil,
        stationId = station.id,
        identifier = identifier,
        name = name,
        rank = offer.rank,
        overrides = {},
        secondsWorked = 0,
        totalPaid = 0,
        hiredAt = now,
        lastShift = nil,
    }
    -- rezervace v paměti ještě před zápisem (zabrání dvojitému přijetí)
    stationEmployees(station.id)[identifier] = employee

    local id = MySQL.insert.await(
        'INSERT INTO `xenon_fuel_employees` (station_id, identifier, name, `rank`, hired_at) VALUES (?, ?, ?, ?, ?)',
        { station.id, identifier, name, offer.rank, now }
    )
    if not id then
        stationEmployees(station.id)[identifier] = nil
        Core.Notify(source, L('error_internal'), 'error')
        return
    end
    employee.id = id

    Core.Notify(source, L('offer_accepted_self', Stations.GetLabel(station)), 'success')
    if fromSource then Core.Notify(fromSource, L('offer_accepted', name), 'success') end
    Employees.PushAccess(identifier, station.id)
end)

---------------------------------------------------------------------------------------------------
-- Správa zaměstnanců
---------------------------------------------------------------------------------------------------
local function canManageTarget(access, employee)
    if access.isOwner then return true end
    local targetRank = Utils.Ranks[employee.rank]
    return targetRank and targetRank.grade < access.grade
end

function Employees.Fire(source, station, access, identifier)
    local employee = Employees.Get(station.id, identifier)
    if not employee then return Core.Fail('error_employee_not_found') end
    if identifier == Bridge.GetIdentifier(source) then return Core.Fail('error_cannot_self') end
    if not canManageTarget(access, employee) then return Core.Fail('error_rank_too_high') end
    Employees.Remove(station.id, identifier, 'fired')
    return Core.Success(nil, 'employee_fired', employee.name)
end

function Employees.Quit(source, station)
    local identifier = Bridge.GetIdentifier(source)
    local employee = Employees.Get(station.id, identifier)
    if not employee then return Core.Fail('error_employee_not_found') end
    Employees.Remove(station.id, identifier, 'quit')
    return Core.Success(nil, 'employee_quit', Stations.GetLabel(station))
end

--- Odstraní zaměstnance (výpověď, propuštění, prodej benzinky)
function Employees.Remove(stationId, identifier, reason)
    local list = Employees.byStation[stationId]
    local employee = list and list[identifier]
    if not employee then return end

    local source = Bridge.GetSourceFromIdentifier(identifier)
    if source and Employees.onDuty[source] and Employees.onDuty[source].stationId == stationId then
        Employees.ClockOut(source, true)
    end

    list[identifier] = nil
    MySQL.update.await('DELETE FROM `xenon_fuel_employees` WHERE station_id = ? AND identifier = ?', { stationId, identifier })

    if source then
        local station = Stations.Get(stationId)
        if reason == 'fired' then
            Core.Notify(source, L('you_were_fired', station and Stations.GetLabel(station) or stationId), 'error')
        end
        Employees.PushAccess(identifier, stationId)
    end
end

function Employees.RemoveAll(stationId)
    local list = Employees.byStation[stationId]
    if not list then return end
    local identifiers = {}
    for identifier in pairs(list) do identifiers[#identifiers + 1] = identifier end
    for _, identifier in ipairs(identifiers) do
        Employees.Remove(stationId, identifier, 'station_sold')
    end
end

function Employees.SetRank(source, station, access, identifier, rankId)
    local employee = Employees.Get(station.id, identifier)
    if not employee then return Core.Fail('error_employee_not_found') end
    local rank = Utils.Ranks[rankId]
    if not rank then return Core.Fail('error_invalid_rank') end
    if identifier == Bridge.GetIdentifier(source) then return Core.Fail('error_cannot_self') end
    if not canManageTarget(access, employee) then return Core.Fail('error_rank_too_high') end
    if not access.isOwner and rank.grade >= access.grade then return Core.Fail('error_rank_too_high') end

    employee.rank = rank.id
    saveEmployee(employee)
    Employees.PushAccess(identifier, station.id)
    local target = Bridge.GetSourceFromIdentifier(identifier)
    if target then Core.Notify(target, L('rank_changed_self', rank.label, Stations.GetLabel(station)), 'info') end
    return Core.Success(nil, 'rank_changed', employee.name, rank.label)
end

--- Individuální oprávnění: true = povolit, false = zakázat, nil = podle hodnosti
function Employees.SetPermissions(source, station, access, identifier, overrides)
    local employee = Employees.Get(station.id, identifier)
    if not employee then return Core.Fail('error_employee_not_found') end
    if identifier == Bridge.GetIdentifier(source) then return Core.Fail('error_cannot_self') end
    if not canManageTarget(access, employee) then return Core.Fail('error_rank_too_high') end
    if type(overrides) ~= 'table' then return Core.Fail('error_invalid_data') end

    local clean = {}
    for perm in pairs(ALL_PERMISSIONS) do
        local value = overrides[perm]
        if value == true or value == false then
            -- nikdo nemůže udělit oprávnění, které sám nemá
            if value == true and not access.isOwner and access.perms[perm] ~= true then
                return Core.Fail('error_cannot_grant')
            end
            clean[perm] = value
        end
    end

    employee.overrides = clean
    saveEmployee(employee)
    Employees.PushAccess(identifier, station.id)
    return Core.Success(nil, 'permissions_saved', employee.name)
end

---------------------------------------------------------------------------------------------------
-- Směny a výplaty
---------------------------------------------------------------------------------------------------
function Employees.ClockIn(source, station)
    local identifier = Bridge.GetIdentifier(source)
    local employee = Employees.Get(station.id, identifier)
    if not employee then return Core.Fail('error_employee_not_found') end
    if Employees.onDuty[source] then return Core.Fail('error_already_on_duty') end

    local dist = Core.PlayerDistance(source, station.cfg.coords)
    if not dist or dist > Config.Payroll.StationDistance then return Core.Fail('error_not_at_station') end

    Employees.onDuty[source] = {
        stationId = station.id,
        identifier = identifier,
        startedAt = os.time(),
        seconds = 0,
        accrued = 0,
        earned = 0,
    }
    Employees.PushAccess(identifier, station.id)
    return Core.Success(nil, 'duty_on', Stations.GetLabel(station))
end

function Employees.ClockOut(source, silent)
    local shift = Employees.onDuty[source]
    if not shift then return Core.Fail('error_not_on_duty') end
    Employees.onDuty[source] = nil

    local employee = Employees.Get(shift.stationId, shift.identifier)
    local now = os.time()
    if employee then
        employee.lastShift = now
        saveEmployee(employee)
    end
    Transactions.LogShift(shift.stationId, shift.identifier, shift.startedAt, now, shift.seconds, shift.earned)

    if not silent then
        Employees.PushAccess(shift.identifier, shift.stationId)
    end
    return Core.Success(nil, 'duty_off', math.floor(shift.seconds / 60), Utils.FormatMoney(shift.earned))
end

function Employees.GetShift(source)
    return Employees.onDuty[source]
end

local function payroll(dt)
    local intervalSeconds = math.max(1, Config.Payroll.Interval) * 60
    for source, shift in pairs(Employees.onDuty) do
        local station = Stations.Get(shift.stationId)
        local employee = station and Employees.Get(shift.stationId, shift.identifier)
        local coords = Core.GetPlayerCoords(source)

        if not station or not employee or not coords or not Bridge.GetPlayer(source) then
            Employees.ClockOut(source, true)
        else
            local dist = #(coords - station.cfg.coords)
            if dist > Config.Payroll.AutoClockOutDistance then
                Employees.ClockOut(source)
                Core.Notify(source, L('duty_auto_off'), 'warning')
            elseif not Config.Payroll.RequireInStation or dist <= Config.Payroll.StationDistance then
                shift.seconds = shift.seconds + dt
                shift.accrued = shift.accrued + dt
                employee.secondsWorked = employee.secondsWorked + dt

                if Config.Features.Payroll and shift.accrued >= intervalSeconds then
                    shift.accrued = shift.accrued - intervalSeconds
                    local rank = Utils.Ranks[employee.rank]
                    local salary = rank and math.floor(rank.salary) or 0
                    if salary > 0 then
                        if Stations.Debit(station, salary, 'salary', employee.identifier, employee.name, rank.label, true) then
                            Bridge.AddMoney(source, Config.Payroll.PayAccount == 'cash' and 'cash' or 'bank', salary, 'xenon_fuel_salary')
                            employee.totalPaid = employee.totalPaid + salary
                            shift.earned = shift.earned + salary
                            Core.Notify(source, L('salary_paid', Utils.FormatMoney(salary), Stations.GetLabel(station)), 'success')
                        else
                            Core.Notify(source, L('salary_no_funds', Stations.GetLabel(station)), 'error')
                            local ownerSource = Bridge.GetSourceFromIdentifier(station.owner)
                            if ownerSource then
                                Core.Notify(ownerSource, L('salary_no_funds_owner', employee.name, Stations.GetLabel(station)), 'error')
                            end
                        end
                    end
                    saveEmployee(employee)
                end
            end
        end
    end
end

function Employees.StartPayrollLoop()
    if not Config.Features.Employees then return end
    CreateThread(function()
        local interval = math.max(10, Config.Payroll.TickInterval)
        while true do
            Wait(interval * 1000)
            if next(Employees.onDuty) then payroll(interval) end
        end
    end)
end

--- Uloží odpracovaný čas všech lidí ve směně (vypnutí resource)
function Employees.SaveAll()
    for source in pairs(Employees.onDuty) do
        Employees.ClockOut(source, true)
    end
end

Bridge.OnPlayerDropped(function(source)
    Employees.offers[source] = nil
    if Employees.onDuty[source] then Employees.ClockOut(source, true) end
end)

AddEventHandler('playerDropped', function()
    local source = source
    Employees.offers[source] = nil
    if Employees.onDuty[source] then Employees.ClockOut(source, true) end
end)
