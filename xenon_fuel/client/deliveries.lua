--[[
    xenon_fuel – klient: rozvoz paliva cisternami
    Průběh: dispečink -> výdej vozidel -> plnění v distribučním skladu -> jízda k benzince
            -> vykládka -> (volitelně) vrácení vozidla
]]

Deliveries = { job = nil }

local enabled = Config.Features.TankerJob and Config.Features.Orders and Config.Orders.Methods.tanker.enabled
local jobCfg = Config.TankerJob
local depot = jobCfg.Depot
local depotPed, depotBlip, routeBlip = nil, nil, nil

if not enabled then
    function Deliveries.CanLoad() return false end
    function Deliveries.CanUnload() return false end
    function Deliveries.LoadTanker() end
    function Deliveries.UnloadTanker() end
    return
end

---------------------------------------------------------------------------------------------------
-- Navigace a HUD zakázky
---------------------------------------------------------------------------------------------------
local function clearRoute()
    if routeBlip and DoesBlipExist(routeBlip) then RemoveBlip(routeBlip) end
    routeBlip = nil
end

local function setRoute(coords, label)
    clearRoute()
    routeBlip = AddBlipForCoord(coords.x, coords.y, coords.z)
    SetBlipSprite(routeBlip, 1)
    SetBlipColour(routeBlip, 3)
    SetBlipRoute(routeBlip, true)
    SetBlipRouteColour(routeBlip, 3)
    BeginTextCommandSetBlipName('STRING')
    AddTextComponentSubstringPlayerName(label)
    EndTextCommandSetBlipName(routeBlip)
end

local function updateJobHud()
    local job = Deliveries.job
    if not job then
        clearRoute()
        Nui.Send('jobhud', { show = false })
        return
    end

    local step, target
    if job.status == 'assigned' then
        step = L('job_step_load')
        target = depot.loading.coords
        setRoute(target, L('blip_loading'))
    elseif job.status == 'loaded' then
        step = L('job_step_deliver', job.station.label)
        target = job.station.coords
        setRoute(target, job.station.label)
    elseif job.status == 'delivered' then
        step = L('job_step_return')
        target = depot.coords
        setRoute(target, depot.label)
    end

    Nui.Send('jobhud', {
        show = true,
        orderId = job.orderId,
        status = job.status,
        step = step,
        station = job.station and job.station.label,
        liters = job.liters,
        reward = job.reward,
        fuel = job.fuel,
    })
end

local function getJobEntities()
    local job = Deliveries.job
    if not job then return nil, nil end
    local truck = job.truckNet and NetworkDoesEntityExistWithNetworkId(job.truckNet) and NetToVeh(job.truckNet) or nil
    local trailer = job.trailerNet and NetworkDoesEntityExistWithNetworkId(job.trailerNet) and NetToVeh(job.trailerNet) or nil
    return truck, trailer
end

local function attachTrailer()
    CreateThread(function()
        local timeout = GetGameTimer() + 10000
        local truck, trailer
        repeat
            truck, trailer = getJobEntities()
            Wait(200)
        until (truck and trailer and truck ~= 0 and trailer ~= 0) or GetGameTimer() > timeout or not Deliveries.job

        if not truck or not trailer or truck == 0 or trailer == 0 then return end
        NetworkRequestControlOfEntity(trailer)
        local controlTimeout = GetGameTimer() + 2000
        while not NetworkHasControlOfEntity(trailer) and GetGameTimer() < controlTimeout do
            Wait(50)
            NetworkRequestControlOfEntity(trailer)
        end
        AttachVehicleToTrailer(truck, trailer, 1.1)
    end)
end

local function startJob(job)
    Deliveries.job = job
    updateJobHud()
    attachTrailer()
end

local function endJob()
    Deliveries.job = nil
    updateJobHud()
end

---------------------------------------------------------------------------------------------------
-- Dispečink (NPC + blip)
---------------------------------------------------------------------------------------------------
local function openBoard()
    local result = Client.CallWithLoading(L('loading_board'), 'getJobBoard')
    if not result.ok then return Notify(result.message, 'error') end
    Nui.Open('board', result.data)
end

local function returnVehicle()
    local result = Client.Call('returnVehicle')
    Notify(result.message, result.ok and 'success' or 'error')
    if result.ok then endJob() end
end

local function cancelJob()
    local result = Client.Call('cancelJob')
    Notify(result.message, result.ok and 'info' or 'error')
    if result.ok then endJob() end
end

local function spawnDepotPed()
    if depotPed and DoesEntityExist(depotPed) then return end
    local cfgPed = depot.ped
    local model = GetHashKey(cfgPed.model)
    if not lib.requestModel(model, 3000) then return end
    depotPed = CreatePed(4, model, cfgPed.coords.x, cfgPed.coords.y, cfgPed.coords.z, cfgPed.coords.w, false, true)
    SetModelAsNoLongerNeeded(model)
    SetEntityInvincible(depotPed, true)
    SetBlockingOfNonTemporaryEvents(depotPed, true)
    FreezeEntityPosition(depotPed, true)
    TaskStartScenarioInPlace(depotPed, 'WORLD_HUMAN_CLIPBOARD', 0, true)

    exports.ox_target:addLocalEntity(depotPed, {
        {
            name = 'xenon_fuel:board',
            icon = 'fa-solid fa-clipboard-list',
            label = L('target_job_board'),
            distance = 2.5,
            onSelect = openBoard,
        },
        {
            name = 'xenon_fuel:return_vehicle',
            icon = 'fa-solid fa-truck-ramp-box',
            label = L('target_return_vehicle'),
            distance = 2.5,
            canInteract = function() return Deliveries.job ~= nil end,
            onSelect = returnVehicle,
        },
        {
            name = 'xenon_fuel:cancel_job',
            icon = 'fa-solid fa-ban',
            label = L('target_cancel_job'),
            distance = 2.5,
            canInteract = function() return Deliveries.job ~= nil and Deliveries.job.status ~= 'delivered' end,
            onSelect = cancelJob,
        },
    })
end

local function deleteDepotPed()
    if depotPed and DoesEntityExist(depotPed) then
        exports.ox_target:removeLocalEntity(depotPed)
        DeleteEntity(depotPed)
    end
    depotPed = nil
end

depotBlip = AddBlipForCoord(depot.coords.x, depot.coords.y, depot.coords.z)
SetBlipSprite(depotBlip, depot.blip.sprite)
SetBlipColour(depotBlip, depot.blip.color)
SetBlipScale(depotBlip, depot.blip.scale)
SetBlipAsShortRange(depotBlip, true)
BeginTextCommandSetBlipName('STRING')
AddTextComponentSubstringPlayerName(depot.label)
EndTextCommandSetBlipName(depotBlip)

lib.points.new({
    coords = depot.coords,
    distance = 60.0,
    onEnter = spawnDepotPed,
    onExit = deleteDepotPed,
})

---------------------------------------------------------------------------------------------------
-- NUI – nabídka zakázek
---------------------------------------------------------------------------------------------------
RegisterNUICallback('board:accept', function(data, cb)
    if Deliveries.job then return cb({ ok = false, message = L('error_job_active') }) end
    local result = Client.Call('acceptJob', type(data) == 'table' and data.orderId)
    cb(result)
    Notify(result.message, result.ok and 'success' or 'error')
    if result.ok then
        Nui.Close('board')
        startJob(result.data)
    end
end)

RegisterNUICallback('board:cancel', function(_, cb)
    cb(1)
    Nui.Close('board')
    cancelJob()
end)

---------------------------------------------------------------------------------------------------
-- Nakládka a vykládka (ox_target na přívěsu)
---------------------------------------------------------------------------------------------------
local function isJobTrailer(entity)
    local job = Deliveries.job
    return job ~= nil and NetworkGetEntityIsNetworked(entity) and NetworkGetNetworkIdFromEntity(entity) == job.trailerNet
end

function Deliveries.CanLoad(entity)
    local job = Deliveries.job
    if not job or job.status ~= 'assigned' or cache.vehicle or not isJobTrailer(entity) then return false end
    return #(GetEntityCoords(entity) - depot.loading.coords) <= depot.loading.radius
end

function Deliveries.CanUnload(entity)
    local job = Deliveries.job
    if not job or job.status ~= 'loaded' or cache.vehicle or not isJobTrailer(entity) or not job.station then return false end
    return #(GetEntityCoords(entity) - job.station.coords) <= job.station.radius
end

function Deliveries.LoadTanker()
    local begin = Client.Call('beginLoad')
    if not begin.ok then return Notify(begin.message, 'error') end
    if not Client.Progress(begin.data.duration * 1000, L('progress_loading'), 'WORLD_HUMAN_CLIPBOARD') then
        return Notify(L('progress_cancelled'), 'warning')
    end
    local result = Client.Call('finishLoad')
    Notify(result.message, result.ok and 'success' or 'error')
    if result.ok then
        Deliveries.job = result.data
        updateJobHud()
    end
end

function Deliveries.UnloadTanker()
    local begin = Client.Call('beginUnload')
    if not begin.ok then return Notify(begin.message, 'error') end
    if not Client.Progress(begin.data.duration * 1000, L('progress_unloading'), 'WORLD_HUMAN_CLIPBOARD') then
        return Notify(L('progress_cancelled'), 'warning')
    end
    local result = Client.Call('finishUnload')
    Notify(result.message, result.ok and 'success' or 'error')
    if result.ok and Deliveries.job then
        Deliveries.job.status = 'delivered'
        updateJobHud()
        Client.PlaySound('complete')
    end
end

RegisterNetEvent('xenon_fuel:client:jobEnded', function(reason)
    if not Deliveries.job then return end
    if reason ~= 'returned' and reason ~= 'cancelled' then
        Notify(L('job_ended_' .. tostring(reason)), 'error')
    end
    endJob()
end)

AddEventHandler('onResourceStop', function(resource)
    if resource ~= GetCurrentResourceName() then return end
    deleteDepotPed()
    clearRoute()
    if depotBlip and DoesBlipExist(depotBlip) then RemoveBlip(depotBlip) end
end)
