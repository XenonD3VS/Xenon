--[[
    xenon_fuel – klient: tankovací pistole, hadice, tankovací UI, animace a průběh tankování
    Veškeré výpočty ceny a množství provádí server – klient pouze zobrazuje.
]]

Refueling = {}

local refuelCfg = Config.Refuel
local holding = nil     -- { pump, nozzle, rope }
local menu = nil        -- otevřené tankovací UI
local session = nil     -- aktivní tankování

---------------------------------------------------------------------------------------------------
-- Pomocné
---------------------------------------------------------------------------------------------------
local function pumpPayload(pump)
    if pump.index then return { index = pump.index } end
    return { x = pump.coords.x, y = pump.coords.y, z = pump.coords.z }
end

local function vehicleLabel(vehicle)
    local display = GetDisplayNameFromVehicleModel(GetEntityModel(vehicle))
    local label = GetLabelText(display)
    if not label or label == 'NULL' then label = display end
    return label
end

local function playAnim(dict, clip, flag, duration)
    if not lib.requestAnimDict(dict, 2000) then return end
    TaskPlayAnim(cache.ped, dict, clip, 2.0, 2.0, duration or -1, flag or 49, 0, false, false, false)
    RemoveAnimDict(dict)
end

local function deleteRope()
    if holding and holding.rope then
        DeleteRope(holding.rope)
        holding.rope = nil
        RopeUnloadTextures()
    end
end

local function createRope(pump, nozzle)
    if not Config.Features.Rope or not pump.entity then return nil end
    RopeLoadTextures()
    local timeout = GetGameTimer() + 2000
    while not RopeAreTexturesLoaded() and GetGameTimer() < timeout do
        Wait(0)
        RopeLoadTextures()
    end
    if not RopeAreTexturesLoaded() then return nil end

    local pumpCoords = GetEntityCoords(pump.entity)
    local top = vector3(pumpCoords.x, pumpCoords.y, pumpCoords.z + refuelCfg.Rope.pumpHeight)
    local length = refuelCfg.HoseLength
    local rope = AddRope(top.x, top.y, top.z, 0.0, 0.0, 0.0, 3.0, refuelCfg.Rope.type, length, 0.0, 1.0, false, false, false, 1.0, true)
    if not rope or rope == 0 then return nil end
    ActivatePhysics(rope)
    Wait(50)
    local nozzlePos = GetOffsetFromEntityInWorldCoords(nozzle, 0.0, -0.033, -0.195)
    AttachEntitiesToRope(rope, pump.entity, nozzle, top.x, top.y, top.z, nozzlePos.x, nozzlePos.y, nozzlePos.z, length, false, false, nil, nil)
    return rope
end

function Refueling.IsHolding()
    return holding ~= nil
end

function Refueling.IsBusy()
    return session ~= nil or menu ~= nil
end

--- Drží hráč pistoli z tohoto stojanu?
function Refueling.IsHoldingFrom(entity, index)
    if not holding then return false end
    if index then return holding.pump.index == index end
    return holding.pump.entity == entity
end

function Refueling.GetHolding()
    return holding
end

---------------------------------------------------------------------------------------------------
-- Pistole
---------------------------------------------------------------------------------------------------
local function holdLoop()
    CreateThread(function()
        local frame = 0
        while holding do
            if refuelCfg.BlockActionsWhileHolding then
                DisableControlAction(0, 23, true)   -- nastoupit do vozidla
                DisableControlAction(0, 24, true)   -- útok
                DisableControlAction(0, 25, true)   -- míření
                DisableControlAction(0, 21, true)   -- sprint
                DisableControlAction(0, 22, true)   -- skok
                DisableControlAction(0, 140, true)
                DisableControlAction(0, 141, true)
                DisableControlAction(0, 142, true)
            end

            frame = frame + 1
            if frame >= 15 then
                frame = 0
                local ped = cache.ped
                local dist = #(GetEntityCoords(ped) - holding.pump.coords)
                if IsEntityDead(ped) or IsPedInAnyVehicle(ped, true) then
                    Refueling.ReturnNozzle(true)
                elseif dist > refuelCfg.HoseLength + 0.5 then
                    Notify(L('hose_too_far'), 'warning')
                    Refueling.ReturnNozzle(true)
                end
            end
            Wait(0)
        end
    end)
end

---@param pump table { entity?, coords, index?, stationId }
function Refueling.TakeNozzle(pump)
    if holding or cache.vehicle then return end
    if not StationsClient.IsOpen(pump.stationId) then
        return Notify(L('error_station_closed'), 'error')
    end

    local ped = cache.ped
    local anim = refuelCfg.Animations.pickup
    TaskTurnPedToFaceCoord(ped, pump.coords.x, pump.coords.y, pump.coords.z, 600)
    Wait(600)
    playAnim(anim.dict, anim.clip, 48, anim.duration)
    Wait(anim.duration)

    local nozzleCfg = refuelCfg.Nozzle
    local model = GetHashKey(nozzleCfg.model)
    if not lib.requestModel(model, 2000) then return end
    local coords = GetEntityCoords(ped)
    local nozzle = CreateObject(model, coords.x, coords.y, coords.z + 0.2, true, true, false)
    SetModelAsNoLongerNeeded(model)
    AttachEntityToEntity(nozzle, ped, GetPedBoneIndex(ped, nozzleCfg.bone),
        nozzleCfg.offset.x, nozzleCfg.offset.y, nozzleCfg.offset.z,
        nozzleCfg.rotation.x, nozzleCfg.rotation.y, nozzleCfg.rotation.z,
        false, true, false, true, 0, true)

    holding = { pump = pump, nozzle = nozzle }
    holding.rope = createRope(pump, nozzle)
    Client.PlaySound('nozzle_take')
    holdLoop()
    Notify(L('nozzle_taken'), 'info')
end

function Refueling.ReturnNozzle(auto)
    if not holding then return end
    if session then TriggerServerEvent('xenon_fuel:server:stopRefuel') end
    if menu then Nui.Close('refuel') end

    deleteRope()
    local nozzle = holding.nozzle
    if nozzle and DoesEntityExist(nozzle) then
        DetachEntity(nozzle, true, true)
        DeleteEntity(nozzle)
    end
    holding = nil
    if not auto then
        local anim = refuelCfg.Animations.pickup
        playAnim(anim.dict, anim.clip, 48, anim.duration)
    end
    Client.PlaySound('nozzle_return')
end

function Refueling.OnLeaveStation(stationId)
    if holding and holding.pump.stationId == stationId then
        Refueling.ReturnNozzle(true)
    end
end

---------------------------------------------------------------------------------------------------
-- Tankovací UI
---------------------------------------------------------------------------------------------------
function Refueling.CanRefuelVehicle(vehicle)
    if not holding or session or menu or cache.vehicle then return false end
    if #(GetEntityCoords(vehicle) - holding.pump.coords) > refuelCfg.MaxVehiclePumpDistance then return false end
    return Utils.GetVehicleProfile(GetEntityModel(vehicle), GetVehicleClass(vehicle)) ~= nil
end

function Refueling.OpenMenu(vehicle)
    if not holding or session or menu then return end
    if not NetworkGetEntityIsNetworked(vehicle) then
        return Notify(L('error_no_vehicle'), 'error')
    end

    local netId = NetworkGetNetworkIdFromEntity(vehicle)
    local class = GetVehicleClass(vehicle)
    local pump = pumpPayload(holding.pump)
    local result = Client.Call('getRefuelQuote', holding.pump.stationId, pump, netId, class)
    if not result.ok then
        return Notify(result.message, 'error')
    end

    menu = { vehicle = vehicle, netId = netId, class = class, pump = pump, stationId = holding.pump.stationId }
    local data = result.data
    data.vehicle.label = vehicleLabel(vehicle)
    Nui.Open('refuel', data)
end

Nui.onClose.refuel = function()
    menu = nil
end

RegisterNUICallback('refuel:confirm', function(data, cb)
    if not menu or session or type(data) ~= 'table' then
        return cb({ ok = false, message = L('error_invalid_data') })
    end
    local current = menu
    local result = Client.Call('startRefuel', {
        stationId = current.stationId,
        pump = current.pump,
        netId = current.netId,
        class = current.class,
        fuelType = data.fuelType,
        amount = data.amount,
        full = data.full == true,
        method = data.method,
    })
    cb(result)
    if result.ok then
        Nui.Close('refuel')
        Refueling.BeginSession(result.data, current.vehicle)
    end
end)

---------------------------------------------------------------------------------------------------
-- Průběh tankování
---------------------------------------------------------------------------------------------------
local cancelKeybind = lib.addKeybind({
    name = 'xenon_fuel_cancel',
    description = L('keybind_cancel'),
    defaultKey = refuelCfg.CancelKey,
    disabled = true,
    onPressed = function()
        if session and not session.stopping then
            session.stopping = true
            TriggerServerEvent('xenon_fuel:server:stopRefuel')
        end
    end,
})

local function currentCancelKey()
    local ok, key = pcall(function() return cancelKeybind:getCurrentKey() end)
    if ok and type(key) == 'string' and key ~= '' then return key end
    return refuelCfg.CancelKey
end

function Refueling.BeginSession(data, vehicle)
    session = {
        id = data.id,
        data = data,
        vehicle = vehicle,
        startedAt = GetGameTimer(),
    }
    local current = session
    local ped = cache.ped
    local anim = refuelCfg.Animations.refuel

    TaskTurnPedToFaceEntity(ped, vehicle, 700)
    cancelKeybind:disable(false)
    Client.PlaySound('pump_start')

    Nui.Send('progress', {
        show = true,
        fuel = data.fuel,
        amount = data.amount,
        price = data.price,
        total = data.total,
        startFuel = data.startFuel,
        capacity = data.capacity,
        rate = data.rate,
        key = currentCancelKey(),
    })

    CreateThread(function()
        Wait(700)
        if session ~= current then return end
        playAnim(anim.dict, anim.clip, anim.flag)

        while session == current do
            local elapsed = (GetGameTimer() - current.startedAt) / 1000
            local delivered = math.min(data.amount, elapsed * data.rate)
            Nui.Send('progress', {
                update = true,
                delivered = delivered,
                cost = math.min(data.total, delivered * data.price),
                fuel = math.min(100, data.startFuel + delivered / data.capacity * 100),
            })

            if not IsEntityPlayingAnim(ped, anim.dict, anim.clip, 3) then
                playAnim(anim.dict, anim.clip, anim.flag)
            end

            if not current.stopping and (not DoesEntityExist(vehicle)
                or #(GetEntityCoords(ped) - GetEntityCoords(vehicle)) > refuelCfg.MaxPlayerVehicleDistance + 1.0) then
                current.stopping = true
                TriggerServerEvent('xenon_fuel:server:stopRefuel')
            end
            Wait(150)
        end
    end)
end

local endMessages = {
    completed = 'success',
    stopped = 'info',
}

RegisterNetEvent('xenon_fuel:client:refuelEnded', function(result)
    if type(result) ~= 'table' then return end
    if session and session.id ~= result.id then return end
    session = nil
    cancelKeybind:disable(true)

    local anim = refuelCfg.Animations.refuel
    StopAnimTask(cache.ped, anim.dict, anim.clip, 2.0)
    Client.PlaySound('pump_stop')
    Nui.Send('progress', { show = false })

    local reasonKey = 'refuel_end_' .. tostring(result.reason)
    local notifyType = endMessages[result.reason] or 'warning'
    if result.liters and result.liters > 0 then
        Notify(L(reasonKey) .. ' ' .. L('refuel_summary', Utils.FormatNumber(result.liters, 2), Utils.FormatMoney(result.total)), notifyType)
    else
        Notify(L(reasonKey), notifyType)
    end

    if result.receipt then
        Nui.Send('receipt', { receipt = result.receipt })
    end
end)

---------------------------------------------------------------------------------------------------
-- Úklid
---------------------------------------------------------------------------------------------------
AddEventHandler('onResourceStop', function(resource)
    if resource ~= GetCurrentResourceName() then return end
    if holding then
        deleteRope()
        if holding.nozzle and DoesEntityExist(holding.nozzle) then DeleteEntity(holding.nozzle) end
        holding = nil
    end
    if session then
        StopAnimTask(cache.ped, refuelCfg.Animations.refuel.dict, refuelCfg.Animations.refuel.clip, 2.0)
    end
end)
