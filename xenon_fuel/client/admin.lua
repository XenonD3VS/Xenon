--[[
    xenon_fuel – admin panel (klient)
    Klient pouze zobrazuje data a předává požadavky. Oprávnění a všechny akce ověřuje server.
]]

AdminClient = { open = false }

local function openPanel()
    if AdminClient.open then return end
    local result = Client.CallWithLoading(L('loading_admin'), 'adminOpen')
    if not result.ok then
        return Notify(result.message, 'error')
    end
    AdminClient.open = true
    Nui.Open('admin', result.data)
end

RegisterNetEvent('xenon_fuel:client:openAdmin', openPanel)

Nui.onClose.admin = function()
    AdminClient.open = false
end

local silent = { refresh = true, plateLookup = true }

RegisterNUICallback('admin:action', function(data, cb)
    if not AdminClient.open or type(data) ~= 'table' or type(data.action) ~= 'string' then
        return cb({ ok = false, message = L('error_invalid_data') })
    end
    local result = Client.Call('adminAction', data.action, data.payload or {})
    cb(result)
    if result.message and (not silent[data.action] or not result.ok) then
        Notify(result.message, result.ok and 'success' or 'error')
    end
    if result.closed then
        Nui.Close('admin')
    end
end)
