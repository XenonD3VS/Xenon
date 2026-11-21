--[[
    xenon_fuel – konfigurace vozidel
    Autor: XenonD3VS

    Kategorie určuje: kapacitu nádrže, spotřebu, rychlost tankování a povolené druhy paliva.
    Kategorie se určuje v pořadí: Config.ModelOverrides -> Config.ElectricModels -> Config.ClassCategories
]]

Config.Categories = {
    car = {
        label = 'Osobní vozidlo',
        capacity = 60,              -- litrů
        consumption = 1.00,
        refuelRate = 2.5,           -- l / s
        fuelTypes = { 'natural95', 'super98', 'lpg' },
    },
    sport = {
        label = 'Sportovní vozidlo',
        capacity = 70,
        consumption = 1.30,
        refuelRate = 2.5,
        fuelTypes = { 'natural95', 'super98' },
    },
    suv = {
        label = 'SUV / Off-road',
        capacity = 80,
        consumption = 1.35,
        refuelRate = 3.0,
        fuelTypes = { 'natural95', 'super98', 'diesel' },
    },
    van = {
        label = 'Dodávka',
        capacity = 75,
        consumption = 1.25,
        refuelRate = 3.0,
        fuelTypes = { 'diesel', 'natural95' },
    },
    truck = {
        label = 'Nákladní vozidlo',
        capacity = 300,
        consumption = 2.20,
        refuelRate = 7.0,
        fuelTypes = { 'diesel' },
    },
    motorcycle = {
        label = 'Motocykl',
        capacity = 17,
        consumption = 0.55,
        refuelRate = 1.5,
        fuelTypes = { 'natural95', 'super98' },
    },
    boat = {
        label = 'Loď',
        capacity = 140,
        consumption = 1.60,
        refuelRate = 4.0,
        fuelTypes = { 'diesel', 'natural95' },
    },
    helicopter = {
        label = 'Vrtulník',
        capacity = 420,
        consumption = 2.10,
        refuelRate = 9.0,
        fuelTypes = { 'jetfuel' },
    },
    plane = {
        label = 'Letadlo',
        capacity = 650,
        consumption = 2.40,
        refuelRate = 12.0,
        fuelTypes = { 'jetfuel' },
    },
    electric = {
        label = 'Elektromobil',
        capacity = 75,              -- kWh
        consumption = 0.90,
        refuelRate = 1.8,           -- kWh / s
        fuelTypes = { 'electric' },
    },
}

-- Třídy vozidel GTA -> kategorie. false = vozidlo palivo nepoužívá (kola, vlaky, přívěsy)
Config.ClassCategories = {
    [0]  = 'car',          -- Compacts
    [1]  = 'car',          -- Sedans
    [2]  = 'suv',          -- SUVs
    [3]  = 'car',          -- Coupes
    [4]  = 'sport',        -- Muscle
    [5]  = 'sport',        -- Sports Classics
    [6]  = 'sport',        -- Sports
    [7]  = 'sport',        -- Super
    [8]  = 'motorcycle',   -- Motorcycles
    [9]  = 'suv',          -- Off-road
    [10] = 'truck',        -- Industrial
    [11] = 'van',          -- Utility
    [12] = 'van',          -- Vans
    [13] = false,          -- Cycles
    [14] = 'boat',         -- Boats
    [15] = 'helicopter',   -- Helicopters
    [16] = 'plane',        -- Planes
    [17] = 'van',          -- Service
    [18] = 'car',          -- Emergency
    [19] = 'truck',        -- Military
    [20] = 'truck',        -- Commercial
    [21] = false,          -- Trains
    [22] = 'sport',        -- Open wheel
}

-- Elektromobily (kategorie 'electric')
Config.ElectricModels = {
    'voltic', 'voltic2', 'raiden', 'neon', 'cyclone', 'cyclone2', 'tezeract', 'khamelion', 'surge',
    'imorgon', 'iwagen', 'omnisegt', 'virtue', 'dilettante', 'dilettante2', 'caddy', 'caddy2', 'caddy3',
    'airtug', 'rcbandito', 'buffalo5', 'coureur', 'envisage', 'powersurge', 'teslax',
}

-- Výjimky pro konkrétní modely (všechny klíče jsou volitelné)
--   category    – přepíše kategorii
--   capacity    – kapacita nádrže
--   consumption – násobič spotřeby (násobí se s kategorií)
--   fuelTypes   – povolené druhy paliva
--   ignore      – vozidlo palivo vůbec nepoužívá
Config.ModelOverrides = {
    phantom  = { category = 'truck', capacity = 400 },
    phantom3 = { category = 'truck', capacity = 400 },
    hauler   = { category = 'truck', capacity = 380 },
    packer   = { category = 'truck', capacity = 380 },
    mule     = { category = 'truck', capacity = 160, consumption = 0.8 },
    benson   = { category = 'truck', capacity = 200, consumption = 0.9 },
    pounder  = { category = 'truck', capacity = 250 },
    bus      = { category = 'truck', capacity = 250, consumption = 0.9 },
    coach    = { category = 'truck', capacity = 280, consumption = 0.9 },
    rumpo    = { category = 'van', fuelTypes = { 'diesel' } },
    sanchez  = { capacity = 9, consumption = 0.8 },
    faggio   = { capacity = 7, consumption = 0.45, fuelTypes = { 'natural95' } },
    faggio2  = { capacity = 7, consumption = 0.45, fuelTypes = { 'natural95' } },
    -- Vozidla bez paliva (přívěsy, kola apod. jsou ignorována automaticky podle třídy)
    tanker   = { ignore = true },
    tanker2  = { ignore = true },
    trailers = { ignore = true },
}
