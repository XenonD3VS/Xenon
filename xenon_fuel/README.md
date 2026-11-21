# xenon_fuel – Advanced Fuel & Gas Station System

**Autor:** XenonD3VS  **Verze:** 1.0.0  **Framework:** ESX Legacy

Kompletní systém paliva a čerpacích stanic pro RP servery: realistická spotřeba, tankování
s pistolí a hadicí, platby s blokací zálohy, účtenky v ox_inventory, vlastnictví benzinek,
management panel, zaměstnanci s hodnostmi a oprávněními, výplaty, sklad, objednávky paliva
a rozvoz cisternami. Vše se ověřuje na serveru.

---

## Obsah

1. [Funkce](#funkce)
2. [Požadavky](#požadavky)
3. [Instalace](#instalace)
4. [Konfigurace](#konfigurace)
5. [Jak to funguje ve hře](#jak-to-funguje-ve-hře)
6. [Příkazy](#příkazy)
7. [Exporty a integrace (garáže apod.)](#exporty-a-integrace)
8. [Databáze](#databáze)
9. [Bezpečnost](#bezpečnost)
10. [Optimalizace](#optimalizace)
11. [Struktura resource](#struktura-resource)
12. [Řešení problémů](#řešení-problémů)

---

## Funkce

**Palivo vozidel**
- Palivo 0–100 % pro každé vozidlo, replikované přes state bag `fuel`.
- Spotřeba podle rychlosti, otáček motoru, kategorie vozidla, konkrétního modelu i druhu paliva.
- Kategorie: osobní, sportovní, SUV, dodávky, nákladní, motocykly, lodě, vrtulníky, letadla, elektromobily.
- Vozidlo bez paliva nelze nastartovat (motor se vypne a vozidlo zablokuje, po natankování se odblokuje).
- Upozornění na nízký stav paliva na nastavitelných hranicích (výchozí 20 %, 10 %, 5 %) včetně zvuku.
- Minimalistický HUD ukazatel paliva (lze vypnout, pokud máš vlastní HUD).
- Ukládání podle SPZ do databáze – hromadně, jen změněné hodnoty, jen hráčská vozidla.

**Čerpací stanice**
- 27 předkonfigurovaných benzinek po celé mapě, 6 typů (standard, prémiová, truck stop, venkovská, přístav, letiště).
- Každá benzinka: vlastní název, lokace, stojany, ceny, sortiment paliv, kapacita skladu, kupní cena.
- Stojany se detekují automaticky podle modelů, nebo je lze definovat ručně (vlastní MLO, přístaviště, letiště).
- 6 druhů paliva: Natural 95, Super 98, Diesel, LPG, Elektřina, Jet A-1 – vlastní ceny, barvy, násobiče spotřeby.

**Tankování**
- Vezmeš pistoli ze stojanu (prop v ruce + hadice), dojdeš k vozidlu a otevřeš tankovací UI.
- Volba druhu paliva (nevhodná paliva jsou zablokována), množství posuvníkem, předvolbami, vlastním číslem nebo plnou nádrží.
- Cena za jednotku, celková cena a odhad doby tankování ještě před potvrzením.
- Platba hotově nebo z banky – před tankováním se zablokuje záloha, po skončení se nevyčerpaná část vrátí.
- Animace, zvuky čerpadla (generované Web Audio API), průběžný displej s litry a cenou.
- Kdykoliv přerušitelné klávesou (výchozí **X**) – platí se jen skutečně natankované množství.
- Automatické ukončení při odchodu od stojanu, pohybu vozidla, nastartování motoru, nastoupení do vozidla.
- Účtenka jako item v ox_inventory (s metadaty) + zobrazení účtenky na obrazovce. Historie tankování `/fuelhistory`.

**Vlastnictví a management**
- Benzinky jsou veřejné nebo vlastněné hráči, limit vlastněných benzinek na hráče.
- Management panel: přehled (KPI, graf tržeb a nákladů za 7 dní, zásoby, poslední prodeje), ceny,
  sklad a objednávky, zaměstnanci, moje směna, finance, prodeje, nastavení (přejmenování, otevřít/zavřít, prodej).
- Firemní účet: příjmy z prodeje, vklady, výběry, objednávky, mzdy, kompletní historie a souhrn zisku.

**Zaměstnanci**
- Nábor hráčů v blízkosti (nabídka práce s potvrzením), propouštění, výpověď.
- Hodnosti s výchozími oprávněními v configu + individuální oprávnění pro každého zaměstnance (povolit / zakázat / podle hodnosti).
- Nikdo nemůže spravovat stejnou či vyšší hodnost ani udělit oprávnění, které sám nemá.
- Směny (příchod / odchod), evidence odpracovaného času (celkem i za posledních 7 dní), automatické výplaty z firemního účtu.

**Admin panel** (`/fueladmin`)
- Přehled: vlastněné stanice, peníze na firemních účtech, tržby všech stanic, graf za 7 dní, nejvýdělečnější stanice, hráči online.
- Benzinky: vyhledávání a filtry, teleport, otevřít/zavřít, nastavení zůstatku, skladu a názvu, výchozí ceny,
  naplnění skladu, převod vlastnictví na online hráče, reset stanice.
- Objednávky: okamžité doručení nebo zrušení s vrácením peněz (i rozjeté rozvozy).
- Živě: probíhající tankování (ukončit s vyúčtováním), rozvozy (zrušit), zaměstnanci ve směně (odhlásit).
- Palivo vozidel: vlastní / nejbližší vozidlo, hromadné doplnění v okolí, palivo podle SPZ (i pro vozidla v garáži).
- Audit log: každá admin akce se ukládá do databáze i do konzole.

**Zásobování**
- Sklad s kapacitou pro každý druh paliva, veřejné benzinky mají neomezené zásoby (nastavitelné).
- Objednávky: externí dodavatel (automatické doručení po X minutách, s poplatkem) nebo cisterna (levnější, rozváží hráči).
- Rozvozová práce: dispečink v distribučním skladu → převzetí zakázky → tahač + cisterna → plnění → jízda na benzinku → vykládka → odměna → vrácení vozidla.
- Kontrola kapacity skladu při objednání i při doručení, sledování stavu objednávky v panelu.
- Rozvoz je volitelný – nevyzvednuté zakázky po čase doručí dodavatel.

---

## Požadavky

| Resource | Verze |
|---|---|
| [es_extended](https://github.com/esx-framework/esx_core) | ESX Legacy 1.9+ |
| [ox_lib](https://github.com/overextended/ox_lib) | 3.x |
| [ox_target](https://github.com/overextended/ox_target) | 1.x |
| [ox_inventory](https://github.com/overextended/ox_inventory) | 2.x |
| [oxmysql](https://github.com/overextended/oxmysql) | 2.x |
| FXServer | OneSync zapnutý (`set onesync on`) |

Žádné další custom scripty nejsou potřeba.

---

## Instalace

1. **Odstraň jiné fuel scripty** (LegacyFuel, ox_fuel, ps-fuel, cdn-fuel…) – dva systémy paliva by si přepisovaly hodnoty.
2. Zkopíruj složku `xenon_fuel` do `resources`.
3. **Databáze:** tabulky se vytvoří automaticky při prvním startu. Pro ruční instalaci spusť `install.sql`.
4. **Item účtenky** – do `ox_inventory/data/items.lua` přidej:
   ```lua
   ['fuel_receipt'] = {
       label = 'Účtenka z čerpací stanice',
       weight = 5,
       stack = false,
       close = true,
       description = 'Doklad o zaplacení paliva',
       client = { export = 'xenon_fuel.useReceipt' },
   },
   ```
   Volitelně přidej obrázek `fuel_receipt.png` do `ox_inventory/web/images/`. Bez itemu script funguje,
   účtenka se jen zobrazí na obrazovce (v konzoli uvidíš upozornění).
5. **server.cfg** – pořadí je důležité:
   ```cfg
   ensure oxmysql
   ensure ox_lib
   ensure es_extended
   ensure ox_target
   ensure ox_inventory
   ensure xenon_fuel
   ```
6. Restartuj server. V konzoli uvidíš `[xenon_fuel] v1.0.0 připraven – XenonD3VS`.

---

## Konfigurace

Konfigurace je rozdělena do tří souborů ve složce `shared/`:

| Soubor | Obsah |
|---|---|
| `config.lua` | framework, zapínání funkcí, platby, druhy paliva, spotřeba, upozornění, HUD, tankování, animace, zvuky, blipy, vlastnictví, sklad, hodnosti a oprávnění, výplaty, objednávky, rozvoz, bezpečnost, admin |
| `config_vehicles.lua` | kategorie vozidel (kapacita, spotřeba, rychlost tankování, paliva), mapování tříd GTA, elektromobily, výjimky modelů |
| `config_stations.lua` | typy benzinek a seznam benzinek |

### Vypnutí funkcí
V `Config.Features` lze vypnout cokoliv: spotřebu, blokaci motoru, ukládání, HUD, upozornění,
vlastnictví, zaměstnance, výplaty, sklad, objednávky, rozvoz cisternami, účtenky, historii, zvuky, hadici, blipy.

### Přidání nové benzinky
Stačí upravit `shared/config_stations.lua` – hlavní kód se nemění:
```lua
Config.Stations['moje_benzinka'] = {
    label = 'Moje benzinka',
    type = 'standard',
    coords = vector3(100.0, 200.0, 30.0),
    radius = 30.0,
    price = 250000,
    fuelTypes = { 'natural95', 'diesel' },
    prices = { natural95 = 1.79 },
    capacity = { natural95 = 20000, diesel = 20000 },
}
```
- `id` (klíč tabulky) po spuštění neměň – pod ním se ukládá vlastnictví, sklad a finance.
- Pro vlastní stojany (MLO s jinými modely, přístav, letiště) použij `pumps = { { coords = vector3(...) }, ... }`.
  Každý stojan může mít vlastní `fuelTypes`.
- Volitelně `management = vector3(...)` – místo pro správu (kancelář / pokladna). Jinak je správa dostupná
  přes ox_target na stojanech (`Config.Ownership.TargetOnPumps`).

### Nový druh paliva
Přidej záznam do `Config.FuelTypes` (cena, velkoobchodní cena, rozsah cen pro vlastníky, barva, násobič spotřeby)
a jeho id do `Config.FuelTypeOrder`. Pak ho přidej kategoriím vozidel a typům benzinek.

### Spotřeba
```
% za sekundu = (Idle + Rpm × otáčky^RpmExponent + Speed × km/h) × kategorie × model × palivo × GlobalMultiplier
```
Výchozí hodnoty odpovídají cca 30–40 minutám jízdy osobním autem na plnou nádrž. Nejrychlejší úprava je
`Config.Consumption.GlobalMultiplier`.

### Hodnosti a oprávnění
`Config.Employees.Ranks` – vlastní hodnosti (`grade` určuje pořadí), mzda za interval a výchozí oprávnění.
Seznam oprávnění je v `Config.Permissions` (popis přímo v configu). Vlastník má vždy všechna oprávnění.

### Distribuční sklad
`Config.TankerJob.Depot` – poloha dispečinku (NPC), místo výdeje vozidel, plnicí stanoviště a radius pro vrácení.
Volitelně omezení na ESX job (`RequiredJob = 'trucker'`).

---

## Jak to funguje ve hře

### Zákazník
1. Zastav u stojanu, **vypni motor** a vystup.
2. Na stojanu (ox_target) zvol **Vzít tankovací pistoli**.
3. Dojdi k vozidlu a zvol **Natankovat vozidlo**.
4. Vyber palivo, množství a způsob platby → **Zaplatit a tankovat**.
5. Tankování přerušíš klávesou **X** (lze změnit v Nastavení → Klávesové zkratky → FiveM).
6. Po dokončení dostaneš účtenku. Pistoli vrátíš na stojan (nebo se vrátí sama, pokud odejdeš).

### Vlastník
- Neobsazenou benzinku koupíš přes ox_target na stojanu (**Koupit čerpací stanici**).
- **Správa čerpací stanice** otevře management panel.
- Prodej státu v sekci Nastavení (dvoukrokové potvrzení) – dostaneš `SellBackPercent` z kupní ceny + zůstatek firemního účtu.

### Zaměstnanec
- Nabídku práce potvrdíš v okně, které se ti zobrazí.
- **Nastoupit do směny** / **Ukončit směnu** přes ox_target na stojanu nebo v panelu (Moje směna).
- Výplata přichází za každý interval ve směně (výchozí 30 min), pokud jsi u benzinky a firma má peníze.

### Řidič cisterny
1. Jeď do distribučního skladu (blip na mapě), u dispečera zvol **Zakázky rozvozu paliva**.
2. Převezmi zakázku – dostaneš tahač s cisternou.
3. U cisterny zvol **Naplnit cisternu**.
4. Doveď cisternu na benzinku (GPS trasa) a zvol **Vyložit palivo**.
5. Odměna přijde na účet. Vozidlo vrať u dispečera.

---

## Příkazy

| Příkaz | Kdo | Popis |
|---|---|---|
| `/fuelhistory` | všichni | historie tankování (kliknutím na řádek zobrazíš účtenku) |
| `/fueladmin` | admin | admin panel |
| `/setfuel [0-100]` | admin | nastaví palivo vozidla, ve kterém sedíš |
| `/fuelreset [id]` | admin | odebere vlastnictví benzinky (bez náhrady) |
| `/fuelstations` | admin | vypíše id všech benzinek do konzole |

Admin přístup: ESX skupiny v `Config.Admin.Groups` **nebo** ACE oprávnění `Config.Admin.Ace`
(např. `add_ace group.admin xenon_fuel.admin allow` v server.cfg). Názvy příkazů lze změnit v `Config.Admin.Commands`.
Všechny admin akce (panel i příkazy) se zapisují do audit logu.

---

## Exporty a integrace

### Server
```lua
exports.xenon_fuel:GetFuel(vehicleOrNetId)            -- number | nil
exports.xenon_fuel:SetFuel(vehicleOrNetId, 0-100)     -- boolean
exports.xenon_fuel:GetPlateFuel(plate)                -- number | nil (z cache nebo DB)
exports.xenon_fuel:SetPlateFuel(plate, 0-100)         -- boolean (uloží se při dalším ukládání)
exports.xenon_fuel:GetStationOwner(stationId)         -- identifier | nil
exports.xenon_fuel:GetStationPrice(stationId, fuelType)
```

### Client
```lua
exports.xenon_fuel:GetFuel(vehicle)          -- aktuální palivo
exports.xenon_fuel:SetFuel(vehicle, value)   -- pouze SNÍŽENÍ (ochrana proti exploitům)
```

### Garáže
Palivo hráčských vozidel se ukládá automaticky podle SPZ – garáž nemusí nic dělat. Pokud garáž chce
nastavit konkrétní hodnotu při spawnu, musí to udělat **na serveru** přes `exports.xenon_fuel:SetFuel(netId, fuel)`
nebo `SetPlateFuel(plate, fuel)`. Klientský export palivo zvýšit nedovolí.

---

## Databáze

| Tabulka | Obsah |
|---|---|
| `xenon_fuel_vehicles` | stav paliva podle SPZ |
| `xenon_fuel_stations` | vlastník, název, firemní účet, otevřeno, ceny, statistiky |
| `xenon_fuel_stock` | skladové zásoby (benzinka × palivo) |
| `xenon_fuel_employees` | zaměstnanci, hodnost, individuální oprávnění, odpracovaný čas, vyplaceno |
| `xenon_fuel_shifts` | historie směn |
| `xenon_fuel_finance` | pohyby na firemních účtech |
| `xenon_fuel_refuels` | historie tankování (hráč i benzinka), čísla účtenek |
| `xenon_fuel_orders` | objednávky paliva a jejich stav |
| `xenon_fuel_admin_log` | audit log admin akcí |

Všechny důležité údaje přežijí restart. Rozjeté rozvozy se po restartu vrátí do nabídky (vozidla po restartu neexistují).

---

## Bezpečnost

- **Server je jediný zdroj pravdy.** Cenu, množství, kapacitu nádrže, aktuální palivo i sklad počítá server.
  Klient posílá jen volbu (druh paliva, požadované množství, platební metoda).
- **Escrow platby:** záloha se strhne atomicky (bez přerušení mezi kontrolou a odečtením), nevyčerpaná část se vrací.
  Při odpojení během tankování se zbytek vrátí na bankovní účet.
- **Každá relace tankování se vyúčtuje právě jednou**, jedno vozidlo může tankovat jen jeden hráč.
- **Průběh tankování běží na serveru** podle času a rychlosti čerpadla – zrychlení na klientovi nic nezmění.
- **Kontroly polohy:** hráč u stojanu, vozidlo u stojanu, hráč u vozidla, vozidlo stojí, motor vypnutý, nikdo neřídí.
- **State bag `fuel`:** klient smí palivo jen snižovat (spotřeba). Každé zvýšení je vráceno a zalogováno.
- **Oprávnění** se kontrolují na serveru u každé akce managementu; vlastnictví a hodnosti se ověřují znovu po každém
  databázovém yieldu.
- **Firemní účet:** všechny pohyby přes jednu funkci s atomickou kontrolou zůstatku, zámky proti dvojkliku, logování.
- **Objednávky a rozvozy:** kontrola kapacity, stavový automat zakázky, minimální doba nakládky/vykládky ověřená
  serverem, odměna se vyplatí jen jednou.
- **Rate limiting** všech citlivých akcí, ošetření NaN/inf/záporných čísel, sanitizace textů.
- **Admin panel:** oprávnění se ověřuje na serveru u každé akce (nejen při otevření), akce mají rate limit
  a zapisují se do audit logu. Pokus o přístup bez oprávnění se loguje.
- Podezřelé požadavky se vypisují do konzole (`Config.Security.LogSuspicious`).

> Spotřebu paliva počítá klient (otáčky motoru nejsou na serveru dostupné) – stejně jako ve všech běžných fuel scriptech.
> Server ale nikdy nedovolí, aby si klient palivo přidal.

---

## Optimalizace

- **Idle resmon 0.00 ms** – smyčka spotřeby běží jen pokud hráč řídí (ox_lib `onCache`), interval 1 s.
- Zóny benzinek přes `lib.points` (jedna sdílená optimalizovaná smyčka ox_lib).
- Interakce výhradně přes ox_target – žádné markery ani kontroly vzdálenosti v každém snímku.
- Synchronizace paliva až po změně o 0,5 % (nastavitelné), HUD se překresluje jen při změně hodnoty.
- Veřejné údaje benzinek přes `GlobalState` (automaticky i pro nově připojené hráče, bez eventů).
- Server: smyčka tankování existuje jen pokud někdo tankuje, výplaty kontrolují jen hráče ve směně.
- Databáze: hromadný zápis paliva jedním dotazem v intervalu, jen změněné hodnoty, jen hráčská vozidla;
  zápisy benzinky jsou sériové a vždy zapíší poslední stav; při vypnutí serveru / restartu se vše uloží.
- NUI bez frameworku a externích závislostí, fonty a ikony jsou součástí resource.

---

## Struktura resource

```
xenon_fuel/
├── fxmanifest.lua
├── install.sql
├── README.md
├── bridge/esx/            # veškerá komunikace s ESX (server + client)
├── shared/
│   ├── config.lua         # hlavní konfigurace
│   ├── config_vehicles.lua
│   ├── config_stations.lua
│   ├── locale.lua         # načítání překladů
│   └── utils.lua          # profily vozidel, sloučení konfigurace benzinek, formátování
├── server/
│   ├── core.lua           # rate limit, zámky, callbacky s ošetřením chyb
│   ├── database.lua       # automatické vytvoření tabulek
│   ├── fuel.lua           # autoritativní stav paliva, ochrana state bagu, ukládání
│   ├── transactions.lua   # historie, finance, graf, směny
│   ├── stations.lua       # stav benzinek, firemní účet, sériové ukládání
│   ├── employees.lua      # nábor, hodnosti, oprávnění, směny, výplaty
│   ├── ownership.lua      # nákup, prodej, přejmenování, reset
│   ├── refueling.lua      # relace tankování, escrow platby, účtenky
│   ├── deliveries.lua     # objednávky, dodavatel, rozvoz cisternami
│   ├── management.lua     # data a akce management panelu
│   ├── admin.lua          # admin panel, audit log
│   ├── commands.lua
│   └── main.lua           # inicializace, uložení při vypnutí
├── client/
│   ├── main.lua           # NUI most, notifikace, zvuky, účtenka z inventáře
│   ├── fuel.lua           # spotřeba, HUD, upozornění, blokace motoru
│   ├── stations.lua       # zóny, blipy, přístupová práva
│   ├── refueling.lua      # pistole, hadice, tankovací UI, animace
│   ├── management.lua     # panel, nákup, nabídky práce
│   ├── deliveries.lua     # rozvozová práce
│   ├── admin.lua          # admin panel
│   └── targets.lua        # ox_target interakce
├── web/                   # NUI (HTML/CSS/JS, fonty Barlow + JetBrains Mono, ikony Lucide)
└── locales/               # cs.json, en.json
```

---

## Řešení problémů

| Problém | Řešení |
|---|---|
| `Chybí závislost …` v konzoli | Zkontroluj pořadí `ensure` v server.cfg. |
| Na stojanu se nezobrazí ox_target | Stojan musí ležet v radiusu benzinky (`radius`) a mít model z `Config.Refuel.PumpModels`. U MLO s jinými modely přidej model nebo definuj `pumps`. |
| „Vozidlo nestojí u stojanu" | Přistav vozidlo blíž (max. `Config.Refuel.MaxVehiclePumpDistance`). |
| „Nejdřív vypni motor" | Motor musí být vypnutý (realismus + ochrana). |
| Neukládá se palivo | `Config.Features.PersistFuel = true`; ukládají se jen vozidla z tabulky `owned_vehicles` (lze změnit `OnlyOwnedVehicles = false`). |
| Účtenka se nepřidá do inventáře | Přidej item `fuel_receipt` do ox_inventory (viz Instalace). |
| Palivo „skáče" zpět | Běží jiný fuel script – odstraň ho. |
| Chci jiný jazyk | `Config.Locale = 'en'` nebo vytvoř vlastní soubor v `locales/`. |

---

© XenonD3VS – všechna práva vyhrazena. Redistribuce nebo přeprodej bez souhlasu autora je zakázán.
Fonty Barlow a JetBrains Mono jsou pod licencí SIL OFL 1.1, ikony Lucide pod licencí ISC.
