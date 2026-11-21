--[[
    xenon_fuel – lokalizace
    Načte locales/<Config.Locale>.json, chybějící klíče doplní z angličtiny.
]]

Locale = {}

local resource = GetCurrentResourceName()
local strings = {}

local function load(lang)
    local raw = LoadResourceFile(resource, ('locales/%s.json'):format(lang))
    if not raw then return nil end
    local ok, data = pcall(json.decode, raw)
    if not ok or type(data) ~= 'table' then
        print(('^1[xenon_fuel] Chyba při načítání locales/%s.json^7'):format(lang))
        return nil
    end
    return data
end

local fallback = load('en') or {}
strings = load(Config.Locale) or {}
for k, v in pairs(fallback) do
    if strings[k] == nil then strings[k] = v end
end

--- Přeloží klíč, volitelně s parametry pro string.format
---@param key string
---@return string
function L(key, ...)
    local str = strings[key]
    if not str then return key end
    if select('#', ...) > 0 then
        local ok, res = pcall(string.format, str, ...)
        if ok then return res end
    end
    return str
end

function Locale.All()
    return strings
end
