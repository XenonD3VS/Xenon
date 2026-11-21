--[[
    xenon_fuel – sdílené pomocné funkce
    Autor: XenonD3VS
]]

Utils = {}

---------------------------------------------------------------------------------------------------
-- Matematika a formátování
---------------------------------------------------------------------------------------------------
function Utils.Round(value, decimals)
    local m = 10 ^ (decimals or 0)
    return math.floor(value * m + 0.5) / m
end

--- Zaokrouhlí dolů na daný počet desetinných míst (nikdy nepřidá palivo navíc)
function Utils.Floor(value, decimals)
    local m = 10 ^ (decimals or 0)
    return math.floor(value * m + 1e-9) / m
end

function Utils.Clamp(value, min, max)
    if value < min then return min end
    if value > max then return max end
    return value
end

--- Bezpečný převod na konečné číslo (odmítne NaN, inf, řetězce apod.)
function Utils.ToNumber(value)
    value = tonumber(value)
    if not value or value ~= value or value == math.huge or value == -math.huge then return nil end
    return value
end

--- Bezpečný převod na celé kladné číslo
function Utils.ToInt(value)
    value = Utils.ToNumber(value)
    if not value then return nil end
    return math.floor(value)
end

function Utils.FormatNumber(value, decimals)
    decimals = decimals or 0
    local negative = value < 0
    value = math.abs(value)
    local str = ('%.' .. decimals .. 'f'):format(value)
    local int, frac = str:match('^(%d+)%.?(%d*)$')
    int = int:reverse():gsub('(%d%d%d)', '%1' .. Config.Currency.thousands):reverse()
    if int:sub(1, #Config.Currency.thousands) == Config.Currency.thousands then
        int = int:sub(#Config.Currency.thousands + 1)
    end
    local out = int
    if frac and frac ~= '' then out = out .. Config.Currency.decimal .. frac end
    return (negative and '-' or '') .. out
end

function Utils.FormatMoney(value, decimals)
    local num = Utils.FormatNumber(math.abs(value), decimals or 0)
    local sign = (value < 0 and num:find('[1-9]')) and '-' or ''
    if Config.Currency.position == 'after' then
        return sign .. num .. ' ' .. Config.Currency.symbol
    end
    return sign .. Config.Currency.symbol .. num
end

function Utils.TrimPlate(plate)
    if type(plate) ~= 'string' then return '' end
    return (plate:gsub('^%s+', ''):gsub('%s+$', '')):upper()
end

--- Normalizace hashe modelu na kladné 32bit číslo (klient a server vrací hashe různě)
function Utils.Hash(model)
    if type(model) == 'string' then model = GetHashKey(model) end
    model = math.tointeger(model) or math.floor(model)
    if model < 0 then model = model + 4294967296 end
    return model
end

function Utils.TableCount(t)
    local n = 0
    for _ in pairs(t) do n = n + 1 end
    return n
end

function Utils.Debug(...)
    if Config.Debug then
        print('^5[xenon_fuel]^7', ...)
    end
end

--- Odstraní z textu nebezpečné znaky (HTML, řídicí znaky) a ořízne délku
function Utils.SanitizeText(text, maxLength)
    if type(text) ~= 'string' then return nil end
    text = text:gsub('[%c<>"`\\]', ''):gsub('^%s+', ''):gsub('%s+$', ''):gsub('%s%s+', ' ')
    if maxLength and #text > maxLength then
        text = text:sub(1, maxLength)
    end
    return text
end

--- Délka UTF-8 řetězce ve znacích
function Utils.Utf8Len(text)
    local ok, len = pcall(utf8.len, text)
    if ok and len then return len end
    return #text
end

---------------------------------------------------------------------------------------------------
-- Druhy paliva
---------------------------------------------------------------------------------------------------
function Utils.SortFuelTypes(list)
    local order = {}
    for i, id in ipairs(Config.FuelTypeOrder) do order[id] = i end
    table.sort(list, function(a, b)
        return (order[a] or 99) < (order[b] or 99)
    end)
    return list
end

function Utils.FuelUnit(fuelType)
    local ft = Config.FuelTypes[fuelType]
    return ft and ft.unit or 'l'
end

---------------------------------------------------------------------------------------------------
-- Vozidla
---------------------------------------------------------------------------------------------------
local overrides, electric, profileCache = {}, {}, {}

for model, data in pairs(Config.ModelOverrides) do
    overrides[Utils.Hash(model)] = data
end
for _, model in ipairs(Config.ElectricModels) do
    electric[Utils.Hash(model)] = true
end

--- Vrátí profil vozidla (kategorie, kapacita, spotřeba, povolená paliva) nebo nil, pokud palivo nepoužívá
---@param model number hash modelu
---@param class number|nil třída vozidla GTA
function Utils.GetVehicleProfile(model, class)
    model = Utils.Hash(model)
    local cacheKey = model .. ':' .. tostring(class)
    local cached = profileCache[cacheKey]
    if cached ~= nil then return cached or nil end

    local override = overrides[model]
    if override and override.ignore then
        profileCache[cacheKey] = false
        return nil
    end

    local categoryName = override and override.category
    if not categoryName and electric[model] then categoryName = 'electric' end
    if not categoryName and class then categoryName = Config.ClassCategories[class] end

    local category = categoryName and Config.Categories[categoryName]
    if not category then
        profileCache[cacheKey] = false
        return nil
    end

    local fuelTypes = {}
    for _, ft in ipairs((override and override.fuelTypes) or category.fuelTypes) do
        if Config.FuelTypes[ft] then fuelTypes[#fuelTypes + 1] = ft end
    end
    local fuelSet = {}
    for _, ft in ipairs(fuelTypes) do fuelSet[ft] = true end

    local profile = {
        category = categoryName,
        label = category.label,
        capacity = (override and override.capacity) or category.capacity,
        consumption = (category.consumption or 1.0) * ((override and override.consumption) or 1.0),
        refuelRate = (override and override.refuelRate) or category.refuelRate or Config.Refuel.DefaultRate,
        fuelTypes = Utils.SortFuelTypes(fuelTypes),
        fuelSet = fuelSet,
    }
    profileCache[cacheKey] = profile
    return profile
end

--- Zda model vozidla ignoruje palivo nezávisle na třídě
function Utils.IsModelIgnored(model)
    local override = overrides[Utils.Hash(model)]
    return override and override.ignore or false
end

---------------------------------------------------------------------------------------------------
-- Benzinky – sloučení konfigurace benzinky s jejím typem
---------------------------------------------------------------------------------------------------
Utils.Stations = {}
Utils.StationIds = {}

local function buildStation(id, cfg)
    local typeName = cfg.type or 'standard'
    local stype = Config.StationTypes[typeName]
    if not stype then
        print(('^3[xenon_fuel] Benzinka %s má neznámý typ "%s", použije se standard.^7'):format(id, typeName))
        typeName, stype = 'standard', Config.StationTypes.standard or {}
    end

    if not cfg.coords then
        print(('^1[xenon_fuel] Benzinka %s nemá nastavené coords – přeskočeno.^7'):format(id))
        return nil
    end

    local station = {
        id = id,
        label = cfg.label or id,
        type = typeName,
        typeLabel = stype.label or typeName,
        coords = vector3(cfg.coords.x, cfg.coords.y, cfg.coords.z),
        radius = (cfg.radius or stype.radius or 30.0) + 0.0,
        purchasable = (cfg.purchasable ~= false) and (stype.purchasable ~= false),
        price = math.floor(cfg.price or stype.price or 200000),
        blip = cfg.blip ~= false,
        management = cfg.management,
        unloadPoint = cfg.unloadPoint or cfg.coords,
        unloadRadius = cfg.unloadRadius or Config.TankerJob.UnloadRadius,
        fuelTypes = {},
        fuelSet = {},
        prices = {},
        capacity = {},
        pumps = 'auto',
    }

    for _, ft in ipairs(cfg.fuelTypes or stype.fuelTypes or { 'natural95' }) do
        local fuel = Config.FuelTypes[ft]
        if fuel and not station.fuelSet[ft] then
            station.fuelTypes[#station.fuelTypes + 1] = ft
            station.fuelSet[ft] = true
            local price = (cfg.prices and cfg.prices[ft]) or (stype.prices and stype.prices[ft]) or fuel.price
            station.prices[ft] = Utils.Clamp(price, fuel.minPrice, fuel.maxPrice)
            station.capacity[ft] = math.floor((cfg.capacity and cfg.capacity[ft]) or (stype.capacity and stype.capacity[ft]) or Config.Stock.DefaultCapacity)
        elseif not fuel then
            print(('^3[xenon_fuel] Benzinka %s: neznámý druh paliva "%s".^7'):format(id, tostring(ft)))
        end
    end
    Utils.SortFuelTypes(station.fuelTypes)

    if type(cfg.pumps) == 'table' then
        station.pumps = {}
        for i, pump in ipairs(cfg.pumps) do
            local coords = pump.coords or pump
            local entry = { index = i, coords = vector3(coords.x, coords.y, coords.z), fuelTypes = nil }
            if pump.fuelTypes then
                entry.fuelTypes, entry.fuelSet = {}, {}
                for _, ft in ipairs(pump.fuelTypes) do
                    if station.fuelSet[ft] then
                        entry.fuelTypes[#entry.fuelTypes + 1] = ft
                        entry.fuelSet[ft] = true
                    end
                end
            end
            station.pumps[i] = entry
        end
    end

    return station
end

for id, cfg in pairs(Config.Stations) do
    local station = buildStation(id, cfg)
    if station then
        Utils.Stations[id] = station
        Utils.StationIds[#Utils.StationIds + 1] = id
    end
end
table.sort(Utils.StationIds)

--- Najde benzinku, v jejíž zóně leží souřadnice
---@param coords vector3
---@param autoOnly boolean|nil pouze benzinky s automatickou detekcí stojanů
function Utils.GetStationAt(coords, autoOnly)
    local best, bestDist
    for _, id in ipairs(Utils.StationIds) do
        local station = Utils.Stations[id]
        if not autoOnly or station.pumps == 'auto' then
            local dist = #(coords - station.coords)
            if dist <= station.radius and (not bestDist or dist < bestDist) then
                best, bestDist = station, dist
            end
        end
    end
    return best
end

---------------------------------------------------------------------------------------------------
-- Hodnosti zaměstnanců
---------------------------------------------------------------------------------------------------
Utils.Ranks = {}
for _, rank in ipairs(Config.Employees.Ranks) do
    Utils.Ranks[rank.id] = rank
end

Utils.PermissionSet = {}
for _, perm in ipairs(Config.Permissions) do
    Utils.PermissionSet[perm] = true
end
