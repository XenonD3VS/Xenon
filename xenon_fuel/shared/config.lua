--[[
    ██╗  ██╗███████╗███╗   ██╗ ██████╗ ███╗   ██╗        ███████╗██╗   ██╗███████╗██╗
    ╚██╗██╔╝██╔════╝████╗  ██║██╔═══██╗████╗  ██║        ██╔════╝██║   ██║██╔════╝██║
     ╚███╔╝ █████╗  ██╔██╗ ██║██║   ██║██╔██╗ ██║        █████╗  ██║   ██║█████╗  ██║
     ██╔██╗ ██╔══╝  ██║╚██╗██║██║   ██║██║╚██╗██║        ██╔══╝  ██║   ██║██╔══╝  ██║
    ██╔╝ ██╗███████╗██║ ╚████║╚██████╔╝██║ ╚████║███████╗██║     ╚██████╔╝███████╗███████╗
    ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝      ╚═════╝ ╚══════╝╚══════╝

    xenon_fuel – Advanced Fuel & Gas Station System
    Autor: XenonD3VS

    Hlavní konfigurace. Vozidla najdeš v config_vehicles.lua, benzinky v config_stations.lua.
]]

Config = {}

---------------------------------------------------------------------------------------------------
-- OBECNÉ
---------------------------------------------------------------------------------------------------
Config.Debug = false                -- vypisuje ladicí informace do konzole (F8 / server konzole)
Config.Locale = 'cs'                -- soubor v /locales (cs, en)

-- Framework. Veškerá komunikace s frameworkem probíhá přes /bridge/<framework>.
-- Aktuálně podporováno: 'esx' (ESX Legacy 1.9+)
Config.Framework = 'esx'
Config.FrameworkResource = 'es_extended'

-- Formátování měny v UI, účtenkách i notifikacích
Config.Currency = {
    symbol = '$',
    position = 'before',            -- 'before' = $1 250 | 'after' = 1 250 $
    thousands = ' ',
    decimal = ',',
}

-- Systém notifikací: 'xenon' (vlastní NUI notifikace v designu scriptu), 'ox_lib', 'esx'
Config.Notify = 'xenon'

---------------------------------------------------------------------------------------------------
-- ZAPÍNÁNÍ / VYPÍNÁNÍ JEDNOTLIVÝCH FUNKCÍ
---------------------------------------------------------------------------------------------------
Config.Features = {
    Consumption     = true,         -- spotřeba paliva při jízdě
    EngineLock      = true,         -- vozidlo bez paliva nelze nastartovat
    PersistFuel     = true,         -- ukládání stavu paliva do databáze (přežije restart)
    Hud             = true,         -- minimalistický ukazatel paliva při řízení
    LowFuelWarnings = true,         -- upozornění na nízký stav paliva
    Ownership       = true,         -- nákup / vlastnictví benzinek hráči
    Employees       = true,         -- zaměstnanci benzinek
    Payroll         = true,         -- automatické výplaty zaměstnanců
    Stock           = true,         -- skladové zásoby (vlastněné benzinky prodávají jen to, co mají na skladě)
    Orders          = true,         -- objednávání paliva do skladu
    TankerJob       = true,         -- rozvoz paliva cisternami hráči (vyžaduje Orders)
    Receipts        = true,         -- účtenka jako item v ox_inventory (vyžaduje item, viz README)
    RefuelHistory   = true,         -- historie tankování hráče (/fuelhistory)
    Sounds          = true,         -- zvukové efekty (generované přímo v NUI, bez externích souborů)
    Rope            = true,         -- hadice mezi stojanem a pistolí (lokální efekt)
    Blips           = true,         -- blipy benzinek na mapě
}

---------------------------------------------------------------------------------------------------
-- PLATBY
---------------------------------------------------------------------------------------------------
Config.Payment = {
    -- Povolené platební metody při tankování
    Methods = { cash = true, bank = true },
    -- Názvy ESX účtů (u ox_inventory je hotovost item 'money', ESX ho synchronizuje s účtem 'money')
    Accounts = { cash = 'money', bank = 'bank' },
    DefaultMethod = 'bank',
    -- Pokud se hráč odpojí během tankování, nevyčerpaná záloha se vrátí na tento účet.
    -- Banka je bezpečnější – ukládá ji přímo ESX při odpojení.
    RefundOnDisconnectAccount = 'bank',
}

---------------------------------------------------------------------------------------------------
-- DRUHY PALIVA
--  price       – výchozí cena za jednotku (veřejné benzinky a nově koupené benzinky)
--  wholesale   – nákupní (velkoobchodní) cena pro objednávky do skladu
--  minPrice / maxPrice – rozsah, ve kterém může vlastník nastavit cenu (kontrolováno server-side)
--  consumption – násobič spotřeby (např. Super 98 = úspornější)
--  unit        – 'l' nebo 'kwh' (jen popisek v UI)
---------------------------------------------------------------------------------------------------
Config.FuelTypes = {
    natural95 = { label = 'Natural 95', short = '95',  color = '#5ccf8f', unit = 'l',   price = 1.89, wholesale = 1.12, minPrice = 1.00, maxPrice = 4.50, consumption = 1.00 },
    super98   = { label = 'Super 98',   short = '98',  color = '#ff7b5c', unit = 'l',   price = 2.19, wholesale = 1.34, minPrice = 1.20, maxPrice = 5.00, consumption = 0.93 },
    diesel    = { label = 'Diesel',     short = 'D',   color = '#e3c565', unit = 'l',   price = 1.99, wholesale = 1.18, minPrice = 1.00, maxPrice = 4.80, consumption = 1.00 },
    lpg       = { label = 'LPG',        short = 'LPG', color = '#62a8ff', unit = 'l',   price = 0.99, wholesale = 0.55, minPrice = 0.50, maxPrice = 2.50, consumption = 1.18 },
    electric  = { label = 'Elektřina',  short = 'EV',  color = '#3fd3dc', unit = 'kwh', price = 0.59, wholesale = 0.30, minPrice = 0.20, maxPrice = 1.80, consumption = 1.00 },
    jetfuel   = { label = 'Jet A-1',    short = 'JET', color = '#b69cff', unit = 'l',   price = 2.49, wholesale = 1.55, minPrice = 1.50, maxPrice = 6.00, consumption = 1.00 },
}

-- Pořadí zobrazení druhů paliva v UI
Config.FuelTypeOrder = { 'natural95', 'super98', 'diesel', 'lpg', 'electric', 'jetfuel' }

---------------------------------------------------------------------------------------------------
-- STAV PALIVA VOZIDEL
---------------------------------------------------------------------------------------------------
Config.Fuel = {
    -- Výchozí množství paliva u vozidla, o kterém server nemá žádný záznam (náhodně v rozsahu)
    DefaultRandom = { min = 25, max = 65 },
    -- Výchozí množství u hráčských vozidel (z owned_vehicles), která ještě nemají záznam
    DefaultOwned = 100,

    Persistence = {
        OnlyOwnedVehicles = true,   -- ukládat jen vozidla, která existují v tabulce owned_vehicles
        OwnedVehiclesTable = 'owned_vehicles',
        SaveInterval = 5,           -- minut – změněné hodnoty se ukládají hromadně jedním dotazem
        MinChange = 0.5,            -- % – menší změna se do DB neukládá
        PurgeAfterDays = 30,        -- záznamy nepoužité X dní se při startu smažou (0 = nikdy)
    },
}

---------------------------------------------------------------------------------------------------
-- SPOTŘEBA
-- Výsledná spotřeba (% nádrže za sekundu):
--   (Idle + Rpm * rpm^RpmExponent + Speed * km/h) * kategorie * model * druh paliva * GlobalMultiplier
-- Kategorie vozidel a jejich násobiče najdeš v config_vehicles.lua
---------------------------------------------------------------------------------------------------
Config.Consumption = {
    Interval = 1000,                -- ms – interval výpočtu (běží jen když hráč řídí)
    GlobalMultiplier = 1.0,
    Idle = 0.0045,                  -- % / s při volnoběhu
    Rpm = 0.040,                    -- % / s při maximálních otáčkách
    RpmExponent = 1.6,
    Speed = 0.00032,                -- % / s za každý km/h
    SyncThreshold = 0.5,            -- % – po jaké změně se stav replikuje na server (šetří síť)
}

---------------------------------------------------------------------------------------------------
-- UPOZORNĚNÍ NA NÍZKÝ STAV PALIVA
---------------------------------------------------------------------------------------------------
Config.Warnings = {
    Thresholds = { 20, 10, 5 },     -- % – upozornění při překročení každé hranice
    Sound = true,                   -- krátký výstražný tón
}

---------------------------------------------------------------------------------------------------
-- HUD (ukazatel paliva při řízení)
---------------------------------------------------------------------------------------------------
Config.Hud = {
    Position = 'bottom-right',      -- 'bottom-right', 'bottom-left', 'top-right', 'top-left'
    Offset = { x = 28, y = 28 },    -- px od okraje
    ShowWhenEngineOff = true,
    LowThreshold = 20,              -- % – ukazatel změní barvu
}

---------------------------------------------------------------------------------------------------
-- TANKOVÁNÍ
---------------------------------------------------------------------------------------------------
Config.Refuel = {
    MinAmount = 1,                  -- minimální množství (l)
    DefaultRate = 2.5,              -- l / s – výchozí rychlost (kategorie ji mohou přepsat)
    ServerTick = 500,               -- ms – interval server-side průběhu tankování

    MaxPlayerPumpDistance = 4.0,    -- m – hráč musí být u stojanu (ověřuje server)
    MaxVehiclePumpDistance = 7.5,   -- m – vozidlo musí stát u stojanu (ověřuje server)
    MaxPlayerVehicleDistance = 4.5, -- m – hráč musí stát u vozidla (ověřuje server)
    MaxVehicleSpeed = 0.6,          -- m/s – vozidlo musí stát
    HoseLength = 7.0,               -- m – při vzdálení od stojanu se pistole vrátí / tankování ukončí

    CancelKey = 'X',                -- klávesa pro přerušení tankování (lze změnit v nastavení hry)

    -- Modely stojanů, na které se automaticky navazuje ox_target (uvnitř zóny benzinky)
    PumpModels = {
        'prop_gas_pump_1a', 'prop_gas_pump_1b', 'prop_gas_pump_1c', 'prop_gas_pump_1d',
        'prop_gas_pump_old2', 'prop_gas_pump_old3', 'prop_vintage_pump',
    },

    Nozzle = {
        model = 'prop_cs_fuel_nozle',
        bone = 18905,               -- levá ruka
        offset = vector3(0.13, 0.04, 0.01),
        rotation = vector3(-42.0, -115.0, -63.42),
    },

    Rope = {
        type = 1,
        pumpHeight = 2.1,           -- výška uchycení hadice nad základnou stojanu
    },

    Animations = {
        pickup = { dict = 'anim@am_hold_up@male', clip = 'shoplift_high', duration = 600 },
        refuel = { dict = 'timetable@gardener@filling_can', clip = 'gar_ig_5_filling_can', flag = 49 },
    },

    -- Zabrání tomu, aby hráč s pistolí v ruce nastoupil do vozidla / sprintoval
    BlockActionsWhileHolding = true,
}

---------------------------------------------------------------------------------------------------
-- ZVUKY (generované v NUI pomocí Web Audio API – žádné externí soubory)
---------------------------------------------------------------------------------------------------
Config.Sounds = {
    Volume = 0.35,                  -- 0.0 – 1.0
    PumpLoop = true,                -- zvuk čerpadla během tankování
    Clicks = true,                  -- cvaknutí pistole při začátku / konci
    Warning = true,                 -- tón při nízkém stavu paliva
}

---------------------------------------------------------------------------------------------------
-- BLIPY
---------------------------------------------------------------------------------------------------
Config.Blips = {
    Sprite = 361,
    Scale = 0.7,
    ShortRange = true,
    Colors = {
        public = 4,                 -- veřejná / nevlastněná benzinka
        owned = 2,                  -- benzinka vlastněná hráčem
        mine = 5,                   -- moje benzinka / kde pracuji
        closed = 40,                -- zavřená benzinka
    },
}

---------------------------------------------------------------------------------------------------
-- VLASTNICTVÍ BENZINEK
---------------------------------------------------------------------------------------------------
Config.Ownership = {
    MaxStationsPerPlayer = 2,
    PurchaseAccounts = { bank = true, cash = false },
    SellBackPercent = 0.60,         -- kolik % kupní ceny dostane hráč při prodeji státu
    StartingStock = 0.25,           -- podíl kapacity skladu, který je naplněn při koupi
    AllowRename = true,
    RenameLength = { min = 3, max = 32 },
    -- Při prodeji benzinky se zůstatek firemního účtu vyplatí vlastníkovi na tento účet
    PayoutAccount = 'bank',
    -- Management je dostupný přes ox_target na stojanech dané benzinky (a volitelně přes
    -- 'management' souřadnice v config_stations.lua)
    TargetOnPumps = true,
}

---------------------------------------------------------------------------------------------------
-- SKLAD
---------------------------------------------------------------------------------------------------
Config.Stock = {
    -- Nevlastněné (veřejné) benzinky mají neomezené zásoby
    PublicUnlimited = true,
    -- Výchozí kapacita skladu pro každý druh paliva (lze přepsat typem nebo konkrétní benzinkou)
    DefaultCapacity = 15000,
}

---------------------------------------------------------------------------------------------------
-- ZAMĚSTNANCI
--  Oprávnění (kontrolováno server-side):
--   view_overview      – přehled benzinky
--   view_transactions  – historie prodejů
--   view_stock         – sklad a objednávky (čtení)
--   manage_prices      – nastavování cen
--   order_fuel         – objednávání paliva (platí se z firemního účtu)
--   cancel_orders      – rušení čekajících objednávek
--   toggle_station     – otevření / zavření benzinky
--   view_finances      – firemní účet a finanční historie
--   deposit            – vklady na firemní účet
--   withdraw           – výběry z firemního účtu
--   manage_employees   – nábor, propouštění, hodnosti, oprávnění (jen nižší hodnosti)
--  Vlastník má vždy všechna oprávnění a navíc může přejmenovat a prodat benzinku.
---------------------------------------------------------------------------------------------------
Config.Permissions = {
    'view_overview', 'view_transactions', 'view_stock', 'manage_prices', 'order_fuel', 'cancel_orders',
    'toggle_station', 'view_finances', 'deposit', 'withdraw', 'manage_employees',
}

Config.Employees = {
    MaxPerStation = 12,
    HireDistance = 10.0,            -- m – kandidát musí stát u náboráře
    OfferTimeout = 45,              -- s – jak dlouho platí nabídka práce

    -- Hodnosti (grade = pořadí; vyšší grade = vyšší pozice)
    Ranks = {
        { id = 'trainee',    label = 'Brigádník',     grade = 1, salary = 120, permissions = { view_overview = true } },
        { id = 'attendant',  label = 'Obsluha',       grade = 2, salary = 220, permissions = { view_overview = true, view_stock = true, view_transactions = true } },
        { id = 'supervisor', label = 'Vedoucí směny', grade = 3, salary = 340, permissions = { view_overview = true, view_stock = true, view_transactions = true, manage_prices = true, order_fuel = true, toggle_station = true, deposit = true } },
        { id = 'manager',    label = 'Manažer',       grade = 4, salary = 480, permissions = { view_overview = true, view_stock = true, view_transactions = true, manage_prices = true, order_fuel = true, cancel_orders = true, toggle_station = true, view_finances = true, deposit = true, manage_employees = true } },
    },
    DefaultRank = 'trainee',
}

Config.Payroll = {
    Interval = 30,                  -- minut odpracovaných ve směně = jedna výplata
    PayAccount = 'bank',
    RequireInStation = true,        -- odpracovaný čas se počítá jen v okolí benzinky
    StationDistance = 120.0,        -- m od středu benzinky
    TickInterval = 60,              -- s – interval kontroly směn (server)
    AutoClockOutDistance = 400.0,   -- m – při vzdálení se směna automaticky ukončí
}

---------------------------------------------------------------------------------------------------
-- OBJEDNÁVKY A ROZVOZ PALIVA
---------------------------------------------------------------------------------------------------
Config.Orders = {
    MinLiters = 500,
    MaxLiters = 20000,              -- max. jedna objednávka (= kapacita cisterny)
    MaxPendingPerStation = 3,
    ProcessInterval = 30,           -- s – kontrola doručení objednávek dodavatelem

    Methods = {
        -- Standardní dodávka externím dodavatelem: automaticky po uplynutí času, s poplatkem
        supplier = { enabled = true, feePerLiter = 0.22, delayMinutes = 20 },
        -- Rozvoz hráčem (cisterna): levnější, část ceny tvoří odměna řidiče
        tanker = {
            enabled = true,
            reward = { base = 400, perLiter = 0.06, max = 2500 },
            -- Pokud zakázku nikdo nepřevezme do X minut, doručí ji dodavatel (0 = nikdy)
            fallbackToSupplierAfter = 90,
        },
    },
}

Config.TankerJob = {
    RequiredJob = false,            -- false = kdokoliv, nebo název ESX jobu, např. 'trucker'
    MaxActiveJobsPerPlayer = 1,
    JobTimeout = 60,                -- minut – po vypršení se zakázka vrátí zpět do nabídky

    Depot = {
        label = 'Distribuční sklad paliv',
        coords = vector3(557.93, -2327.90, 5.83),
        ped = { model = 's_m_m_trucker_01', coords = vector4(557.93, -2327.90, 4.83, 230.0) },
        blip = { sprite = 477, color = 47, scale = 0.75 },
        -- Místo výdeje vozidel (najde se nejbližší silniční uzel)
        vehicleSpawn = vector4(571.54, -2309.70, 5.90, 0.0),
        -- Plnicí stanoviště cisteren
        loading = { coords = vector3(571.54, -2309.70, 5.90), radius = 45.0 },
        returnRadius = 45.0,
    },

    Vehicles = { truck = 'phantom', trailer = 'tanker' },
    LoadTime = 15,                  -- s
    UnloadTimePer1000 = 2.0,        -- s za každých 1000 l
    UnloadTimeLimits = { min = 10, max = 60 },
    UnloadRadius = 35.0,            -- m od středu benzinky (lze přepsat u benzinky)
}

---------------------------------------------------------------------------------------------------
-- BEZPEČNOST
---------------------------------------------------------------------------------------------------
Config.Security = {
    ActionCooldown = 750,           -- ms – minimální rozestup citlivých akcí jednoho hráče
    MaxTransactionAmount = 10000000,
    LogSuspicious = true,           -- logovat podezřelé požadavky do konzole
    -- Klient smí stav paliva pouze snižovat (spotřeba). Zvýšení provádí jen server.
    RejectClientFuelIncrease = true,
}

---------------------------------------------------------------------------------------------------
-- ADMIN
---------------------------------------------------------------------------------------------------
Config.Admin = {
    Groups = { 'admin', 'superadmin' }, -- ESX skupiny s přístupem k admin příkazům
    Commands = {
        setFuel = 'setfuel',            -- /setfuel [0-100]
        resetStation = 'fuelreset',     -- /fuelreset [stationId]
        listStations = 'fuelstations',  -- /fuelstations
        history = 'fuelhistory',        -- /fuelhistory (pro všechny hráče)
    },
}

---------------------------------------------------------------------------------------------------
-- HISTORIE
---------------------------------------------------------------------------------------------------
Config.History = {
    PlayerLimit = 25,               -- počet záznamů v historii tankování hráče
    StationPageSize = 25,           -- záznamů na stránku v managementu
    ChartDays = 7,                  -- dnů v grafu tržeb
}
