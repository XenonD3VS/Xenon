--[[
    xenon_fuel – klient: NUI most, notifikace, zvuky, společné pomocné funkce
    Autor: XenonD3VS
]]

Client = {}
Nui = { views = {}, onClose = {} }

---------------------------------------------------------------------------------------------------
-- NUI
---------------------------------------------------------------------------------------------------
function Nui.Send(action, data)
    SendNUIMessage({ action = action, data = data })
end

local function updateFocus()
    local hasView = next(Nui.views) ~= nil
    SetNuiFocus(hasView, hasView)
end

--- Otevře okno vyžadující kurzor
function Nui.Open(view, data)
    Nui.views[view] = true
    updateFocus()
    Nui.Send('open', { view = view, data = data })
end

--- Zavře okno (volá se z Lua strany)
function Nui.Close(view)
    if not Nui.views[view] then return end
    Nui.views[view] = nil
    updateFocus()
    Nui.Send('close', { view = view })
    local handler = Nui.onClose[view]
    if handler then handler() end
end

function Nui.IsOpen(view)
    return Nui.views[view] == true
end

function Nui.CloseAll()
    for view in pairs(Nui.views) do
        Nui.views[view] = nil
        local handler = Nui.onClose[view]
        if handler then handler() end
    end
    SetNuiFocus(false, false)
    Nui.Send('closeAll')
end

-- Okno zavřené uživatelem v UI (Esc / křížek)
RegisterNUICallback('close', function(data, cb)
    cb(1)
    local view = type(data) == 'table' and data.view
    if view and Nui.views[view] then
        Nui.views[view] = nil
        updateFocus()
        local handler = Nui.onClose[view]
        if handler then handler() end
    end
end)

local function buildInit()
    local fuelTypes = {}
    for id, fuel in pairs(Config.FuelTypes) do
        fuelTypes[id] = { label = fuel.label, short = fuel.short, color = fuel.color, unit = fuel.unit }
    end
    local ranks = {}
    for _, rank in ipairs(Config.Employees.Ranks) do
        ranks[#ranks + 1] = { id = rank.id, label = rank.label, grade = rank.grade, salary = rank.salary }
    end
    return {
        locale = Locale.All(),
        config = {
            currency = Config.Currency,
            fuelTypes = fuelTypes,
            fuelOrder = Config.FuelTypeOrder,
            hud = Config.Hud,
            hudEnabled = Config.Features.Hud,
            sounds = {
                enabled = Config.Features.Sounds,
                volume = Config.Sounds.Volume,
                pumpLoop = Config.Sounds.PumpLoop,
                clicks = Config.Sounds.Clicks,
                warning = Config.Sounds.Warning,
            },
            permissions = Config.Permissions,
            ranks = ranks,
            cancelKey = Config.Refuel.CancelKey,
            payroll = Config.Payroll.Interval,
            adminLogLimit = Config.Admin.LogLimit,
        },
    }
end

RegisterNUICallback('ready', function(_, cb)
    cb(1)
    Nui.Send('init', buildInit())
end)

---------------------------------------------------------------------------------------------------
-- Notifikace a zvuky
---------------------------------------------------------------------------------------------------
local oxTypes = { info = 'inform', success = 'success', error = 'error', warning = 'warning' }

function Notify(message, notifyType)
    if not message or message == '' then return end
    notifyType = notifyType or 'info'
    if Config.Notify == 'ox_lib' then
        lib.notify({ title = 'Fuel', description = message, type = oxTypes[notifyType] or 'inform' })
    elseif Config.Notify == 'esx' then
        Bridge.Notify(message, notifyType)
    else
        Nui.Send('notify', { message = message, type = notifyType })
    end
end

RegisterNetEvent('xenon_fuel:client:notify', function(message, notifyType)
    Notify(message, notifyType)
end)

function Client.PlaySound(name)
    if not Config.Features.Sounds then return end
    Nui.Send('sound', { name = name })
end

---------------------------------------------------------------------------------------------------
-- Volání serveru – vždy vrací tabulku { ok, message, data }
---------------------------------------------------------------------------------------------------
function Client.Call(name, ...)
    local result = lib.callback.await('xenon_fuel:server:' .. name, false, ...)
    if type(result) ~= 'table' then
        return { ok = false, error = 'error_internal', message = L('error_internal') }
    end
    return result
end

--- Volání serveru s načítací animací (zobrazí se jen pokud odpověď trvá déle než ~140 ms)
function Client.CallWithLoading(label, name, ...)
    Nui.Send('loading', { show = true, label = label })
    local result = Client.Call(name, ...)
    Nui.Send('loading', { show = false })
    return result
end

--- Vlastní průběh akce (nakládka / vykládka) v designu scriptu. Vrací true po dokončení.
local progressActive = false
function Client.Progress(duration, label, scenario)
    if progressActive then return false end
    progressActive = true
    local ped = cache.ped
    if scenario then TaskStartScenarioInPlace(ped, scenario, 0, true) end

    local finishAt = GetGameTimer() + duration
    local cancelled = false
    Nui.Send('action', { show = true, label = label, duration = duration, key = 'X' })

    while GetGameTimer() < finishAt do
        DisableControlAction(0, 30, true)
        DisableControlAction(0, 31, true)
        DisableControlAction(0, 21, true)
        DisableControlAction(0, 22, true)
        DisableControlAction(0, 23, true)
        DisableControlAction(0, 24, true)
        DisableControlAction(0, 25, true)
        if IsDisabledControlJustPressed(0, 73) or IsEntityDead(ped) then -- X
            cancelled = true
            break
        end
        Wait(0)
    end

    Nui.Send('action', { show = false })
    if scenario then ClearPedTasks(ped) end
    progressActive = false
    return not cancelled
end

---------------------------------------------------------------------------------------------------
-- Účtenka z inventáře (ox_inventory: client.export = 'xenon_fuel.useReceipt')
---------------------------------------------------------------------------------------------------
exports('useReceipt', function(_, slot)
    local receipt = slot and slot.metadata and slot.metadata.receipt
    if type(receipt) == 'table' then
        Nui.Send('receipt', { receipt = receipt, fromItem = true })
    end
end)

---------------------------------------------------------------------------------------------------
-- Historie tankování
---------------------------------------------------------------------------------------------------
RegisterNetEvent('xenon_fuel:client:openHistory', function()
    local result = Client.CallWithLoading(L('loading_history'), 'getHistory')
    if not result.ok then
        return Notify(result.message, 'error')
    end
    Nui.Open('history', { rows = result.data })
end)

---------------------------------------------------------------------------------------------------
-- Úklid při zastavení resource
---------------------------------------------------------------------------------------------------
AddEventHandler('onResourceStop', function(resource)
    if resource ~= GetCurrentResourceName() then return end
    SetNuiFocus(false, false)
end)
