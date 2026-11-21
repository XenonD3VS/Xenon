--[[
    xenon_fuel – příkazy
]]

local commands = Config.Admin.Commands

local function reply(source, message, notifyType)
    if source == 0 then
        print('[xenon_fuel] ' .. message)
    else
        Core.Notify(source, message, notifyType)
    end
end

local function requireAdmin(source)
    if Bridge.IsAdmin(source) then return true end
    reply(source, L('error_no_permission'), 'error')
    return false
end

if commands.panel then
    lib.addCommand(commands.panel, {
        help = L('cmd_panel_help'),
    }, function(source)
        if source == 0 or not requireAdmin(source) then return end
        TriggerClientEvent('xenon_fuel:client:openAdmin', source)
    end)
end

if commands.setFuel then
    lib.addCommand(commands.setFuel, {
        help = L('cmd_setfuel_help'),
        params = { { name = 'amount', type = 'number', help = '0 - 100', optional = true } },
    }, function(source, args)
        if source == 0 or not requireAdmin(source) then return end
        local ped = GetPlayerPed(source)
        local vehicle = GetVehiclePedIsIn(ped, false)
        if vehicle == 0 then
            return reply(source, L('error_not_in_vehicle'), 'error')
        end
        local amount = Utils.Clamp(args.amount or 100, 0, 100)
        Fuel.Set(vehicle, amount)
        Admin.Audit(source, 'set_fuel', Utils.TrimPlate(GetVehicleNumberPlateText(vehicle)), amount)
        reply(source, L('cmd_setfuel_done', amount), 'success')
    end)
end

if commands.resetStation then
    lib.addCommand(commands.resetStation, {
        help = L('cmd_reset_help'),
        params = { { name = 'station', type = 'string', help = 'ID benzinky (/' .. (commands.listStations or 'fuelstations') .. ')' } },
    }, function(source, args)
        if not requireAdmin(source) then return end
        local station = Stations.Get(args.station)
        if not station then return reply(source, L('error_invalid_station'), 'error') end
        Ownership.Reset(station)
        Admin.Audit(source, 'reset_station', station.id, 'command')
        reply(source, L('cmd_reset_done', station.cfg.label), 'success')
    end)
end

if commands.listStations then
    lib.addCommand(commands.listStations, {
        help = L('cmd_list_help'),
    }, function(source)
        if not requireAdmin(source) then return end
        local lines = {}
        for _, id in ipairs(Utils.StationIds) do
            local station = Stations.Get(id)
            lines[#lines + 1] = ('%s – %s – %s'):format(id, Stations.GetLabel(station), station.ownerName or L('public'))
        end
        print('^5[xenon_fuel] Benzinky:^7\n' .. table.concat(lines, '\n'))
        reply(source, L('cmd_list_done', #lines), 'info')
    end)
end

if commands.history and Config.Features.RefuelHistory then
    lib.addCommand(commands.history, {
        help = L('cmd_history_help'),
    }, function(source)
        if source == 0 then return end
        TriggerClientEvent('xenon_fuel:client:openHistory', source)
    end)
end
