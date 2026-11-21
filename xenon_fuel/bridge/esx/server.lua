--[[
    xenon_fuel – ESX bridge (server)
    Veškerá komunikace s frameworkem je soustředěna zde.
]]

if Config.Framework ~= 'esx' then return end

local ESX = exports[Config.FrameworkResource]:getSharedObject()

Bridge = {}

local adminGroups = {}
for _, group in ipairs(Config.Admin.Groups) do adminGroups[group] = true end

local function accountName(method)
    return Config.Payment.Accounts[method] or method
end

function Bridge.GetPlayer(source)
    return ESX.GetPlayerFromId(source)
end

function Bridge.GetIdentifier(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    return xPlayer and xPlayer.identifier or nil
end

function Bridge.GetName(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return GetPlayerName(source) or ('#' .. tostring(source)) end
    local ok, name = pcall(xPlayer.getName)
    if ok and name and name ~= '' then return name end
    return GetPlayerName(source) or xPlayer.identifier
end

function Bridge.GetSourceFromIdentifier(identifier)
    if not identifier then return nil end
    local xPlayer = ESX.GetPlayerFromIdentifier(identifier)
    return xPlayer and xPlayer.source or nil
end

---@param method 'cash'|'bank'
function Bridge.GetMoney(source, method)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return 0 end
    local account = xPlayer.getAccount(accountName(method))
    return account and math.floor(account.money) or 0
end

--- Odebere peníze. Vrací true pouze pokud hráč měl dostatek a peníze byly odečteny.
function Bridge.RemoveMoney(source, method, amount, reason)
    amount = math.floor(amount)
    if amount <= 0 then return true end
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return false end
    local name = accountName(method)
    local account = xPlayer.getAccount(name)
    if not account or account.money < amount then return false end
    xPlayer.removeAccountMoney(name, amount, reason)
    return true
end

function Bridge.AddMoney(source, method, amount, reason)
    amount = math.floor(amount)
    if amount <= 0 then return true end
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return false end
    xPlayer.addAccountMoney(accountName(method), amount, reason)
    return true
end

--- Připíše peníze na bankovní účet hráče, který již není online (záloha při pádu / odpojení).
function Bridge.AddOfflineBank(identifier, amount)
    amount = math.floor(amount)
    if amount <= 0 or not identifier then return end
    MySQL.update(
        "UPDATE users SET accounts = JSON_SET(accounts, '$.bank', COALESCE(JSON_EXTRACT(accounts, '$.bank'), 0) + ?) WHERE identifier = ?",
        { amount, identifier }
    )
end

function Bridge.GetJob(source)
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return nil end
    local job = xPlayer.getJob()
    return job and job.name or nil
end

function Bridge.IsAdmin(source)
    if source == 0 then return true end
    local xPlayer = ESX.GetPlayerFromId(source)
    if not xPlayer then return false end
    if adminGroups[xPlayer.getGroup()] == true then return true end
    return Config.Admin.Ace and IsPlayerAceAllowed(tostring(source), Config.Admin.Ace) or false
end

function Bridge.GetPlayers()
    local list = {}
    for _, xPlayer in pairs(ESX.GetExtendedPlayers()) do
        list[#list + 1] = xPlayer.source
    end
    return list
end

--- Zda vozidlo s danou SPZ vlastní nějaký hráč
function Bridge.IsVehicleOwned(plate)
    local result = MySQL.scalar.await(
        ('SELECT 1 FROM `%s` WHERE plate = ? LIMIT 1'):format(Config.Fuel.Persistence.OwnedVehiclesTable),
        { plate }
    )
    return result ~= nil
end

function Bridge.OnPlayerLoaded(cb)
    AddEventHandler('esx:playerLoaded', function(source)
        cb(source)
    end)
end

--- Volá se ještě předtím, než ESX hráče uloží a odstraní – peníze lze bezpečně vrátit.
function Bridge.OnPlayerDropped(cb)
    AddEventHandler('esx:playerDropped', function(source)
        cb(source)
    end)
end
