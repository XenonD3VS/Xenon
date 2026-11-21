--[[
    xenon_fuel – konfigurace čerpacích stanic
    Autor: XenonD3VS

    PŘIDÁNÍ NOVÉ BENZINKY
    ---------------------
    Stačí přidat nový záznam do Config.Stations. Klíč (id) musí být unikátní a po spuštění serveru
    ho už neměň – pod tímto id se ukládá vlastnictví, sklad i finance.

    Všechny hodnoty kromě label a coords jsou volitelné. Pokud nejsou uvedeny, převezmou se z typu
    benzinky (Config.StationTypes) a poté z globálního configu.

    Config.Stations['moje_benzinka'] = {
        label = 'Moje benzinka',
        type = 'standard',                      -- typ z Config.StationTypes
        coords = vector3(x, y, z),              -- střed benzinky (blip a zóna)
        radius = 30.0,                          -- poloměr zóny, ve které fungují stojany
        purchasable = true,                     -- lze koupit hráčem
        price = 250000,                         -- kupní cena
        fuelTypes = { 'natural95', 'diesel' },  -- prodávané druhy paliva
        prices = { natural95 = 1.79 },          -- výchozí ceny (jinak z Config.FuelTypes)
        capacity = { natural95 = 20000 },       -- kapacita skladu pro jednotlivé druhy
        blip = true,                            -- zobrazit blip
        management = vector3(x, y, z),          -- volitelné místo pro správu (kancelář / pokladna)
        unloadPoint = vector3(x, y, z),         -- volitelné místo vykládky cisterny (jinak střed)

        -- Stojany: 'auto' = automatická detekce modelů z Config.Refuel.PumpModels uvnitř zóny.
        -- Nebo seznam vlastních stojanů (např. MLO s vlastními modely, přístaviště, letiště):
        pumps = {
            { coords = vector3(x, y, z), fuelTypes = { 'diesel' } },      -- fuelTypes volitelné
            { coords = vector3(x, y, z) },
        },
    }
]]

---------------------------------------------------------------------------------------------------
-- TYPY BENZINEK – výchozí hodnoty pro skupiny benzinek
---------------------------------------------------------------------------------------------------
Config.StationTypes = {
    standard = {
        label = 'Čerpací stanice',
        fuelTypes = { 'natural95', 'super98', 'diesel', 'lpg' },
        capacity = { natural95 = 15000, super98 = 8000, diesel = 15000, lpg = 6000 },
        price = 225000,
        radius = 30.0,
    },
    premium = {
        label = 'Prémiová čerpací stanice',
        fuelTypes = { 'natural95', 'super98', 'diesel', 'lpg', 'electric' },
        capacity = { natural95 = 18000, super98 = 14000, diesel = 15000, lpg = 6000, electric = 12000 },
        prices = { super98 = 2.29 },
        price = 340000,
        radius = 32.0,
    },
    truckstop = {
        label = 'Truck stop',
        fuelTypes = { 'natural95', 'diesel', 'lpg' },
        capacity = { natural95 = 15000, diesel = 40000, lpg = 6000 },
        prices = { diesel = 1.89 },
        price = 390000,
        radius = 40.0,
    },
    rural = {
        label = 'Venkovská pumpa',
        fuelTypes = { 'natural95', 'diesel' },
        capacity = { natural95 = 10000, diesel = 10000 },
        prices = { natural95 = 1.95, diesel = 2.05 },
        price = 150000,
        radius = 28.0,
    },
    marina = {
        label = 'Přístavní čerpací stanice',
        fuelTypes = { 'natural95', 'diesel' },
        capacity = { natural95 = 12000, diesel = 20000 },
        price = 280000,
        radius = 25.0,
    },
    airfield = {
        label = 'Letištní čerpací stanice',
        fuelTypes = { 'jetfuel' },
        capacity = { jetfuel = 40000 },
        price = 450000,
        radius = 40.0,
    },
}

---------------------------------------------------------------------------------------------------
-- BENZINKY
---------------------------------------------------------------------------------------------------
Config.Stations = {
    -- Los Santos – město
    ltd_davis = {
        label = 'LTD Grove Street',
        type = 'premium',
        coords = vector3(-70.21, -1761.79, 29.53),
    },
    globe_davis = {
        label = 'Globe Oil Davis',
        type = 'standard',
        coords = vector3(176.63, -1562.03, 29.26),
    },
    xero_strawberry = {
        label = 'Xero Strawberry',
        type = 'standard',
        coords = vector3(265.65, -1261.31, 29.29),
    },
    ron_lamesa = {
        label = 'RON La Mesa',
        type = 'standard',
        coords = vector3(819.65, -1028.85, 26.40),
    },
    ron_elburro = {
        label = 'RON El Burro Heights',
        type = 'standard',
        coords = vector3(1208.95, -1402.57, 35.22),
    },
    ltd_mirrorpark = {
        label = 'LTD Mirror Park',
        type = 'premium',
        coords = vector3(1181.38, -330.85, 69.32),
    },
    globe_vinewood = {
        label = 'Globe Oil Vinewood',
        type = 'premium',
        coords = vector3(620.84, 269.10, 103.09),
    },
    ltd_littleseoul = {
        label = 'LTD Little Seoul',
        type = 'premium',
        coords = vector3(-724.62, -935.16, 19.21),
    },
    xero_littleseoul = {
        label = 'Xero Calais Avenue',
        type = 'standard',
        coords = vector3(-526.02, -1211.00, 18.18),
    },
    xero_davisave = {
        label = 'Xero Davis Avenue',
        type = 'standard',
        coords = vector3(-319.29, -1471.72, 30.55),
    },
    ron_morningwood = {
        label = 'RON Morningwood',
        type = 'standard',
        coords = vector3(-1437.62, -276.75, 46.21),
    },
    xero_pacificbluffs = {
        label = 'Xero Pacific Bluffs',
        type = 'standard',
        coords = vector3(-2096.24, -320.29, 13.17),
    },
    ltd_banham = {
        label = 'LTD Banham Canyon',
        type = 'standard',
        coords = vector3(-1800.38, 803.66, 138.65),
    },

    -- Okolí / dálnice
    ron_palomino = {
        label = 'RON Palomino Freeway',
        type = 'standard',
        coords = vector3(2581.32, 362.04, 108.47),
    },
    ron_zancudo = {
        label = 'RON Route 68 West',
        type = 'rural',
        coords = vector3(-2555.00, 2334.40, 33.08),
    },
    globe_route68 = {
        label = 'Globe Oil Route 68',
        type = 'truckstop',
        coords = vector3(49.42, 2778.79, 58.04),
    },
    xero_harmony = {
        label = 'Xero Harmony',
        type = 'rural',
        coords = vector3(263.89, 2606.46, 44.98),
    },
    ron_route68 = {
        label = 'RON Route 68',
        type = 'rural',
        coords = vector3(1039.96, 2671.13, 39.55),
    },
    globe_senora = {
        label = 'Globe Oil Grand Senora',
        type = 'rural',
        coords = vector3(1207.26, 2660.18, 37.90),
    },
    ron_senorafwy = {
        label = 'RON Senora Freeway',
        type = 'truckstop',
        coords = vector3(2539.69, 2594.19, 37.94),
    },
    xero_senora = {
        label = 'Xero Senora Freeway',
        type = 'truckstop',
        coords = vector3(2679.86, 3263.95, 55.24),
    },
    xero_sandy = {
        label = 'Xero Sandy Shores',
        type = 'standard',
        coords = vector3(2005.06, 3773.89, 32.40),
    },
    flywheels_sandy = {
        label = 'Sandy Shores Airfield',
        type = 'rural',
        coords = vector3(1784.32, 3330.55, 41.25),
    },
    ltd_grapeseed = {
        label = 'LTD Grapeseed',
        type = 'standard',
        coords = vector3(1687.16, 4929.39, 42.08),
    },
    ron_braddock = {
        label = 'RON Braddock Pass',
        type = 'truckstop',
        coords = vector3(1701.31, 6416.03, 32.76),
    },
    globe_paleto = {
        label = 'Globe Oil Paleto Bay',
        type = 'standard',
        coords = vector3(179.86, 6602.84, 31.87),
    },
    xero_paleto = {
        label = 'Xero Paleto Bay',
        type = 'standard',
        coords = vector3(-94.46, 6419.59, 31.49),
    },
}
