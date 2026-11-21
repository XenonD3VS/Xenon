--[[
    xenon_fuel – ESX bridge (client)
]]

if Config.Framework ~= 'esx' then return end

local ESX = exports[Config.FrameworkResource]:getSharedObject()

Bridge = {}

function Bridge.IsLoaded()
    return ESX.IsPlayerLoaded()
end

function Bridge.Notify(message, notifyType)
    ESX.ShowNotification(message, notifyType)
end

function Bridge.OnPlayerLoaded(cb)
    RegisterNetEvent('esx:playerLoaded', function()
        cb()
    end)
end

function Bridge.OnPlayerLogout(cb)
    RegisterNetEvent('esx:onPlayerLogout', function()
        cb()
    end)
end
