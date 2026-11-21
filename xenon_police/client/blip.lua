-- Volitelny blip na mape pro xenon_police (LSPD).
-- Vypnuti: nastav ENABLE_BLIP = false.
local ENABLE_BLIP = true

-- Hlavni vchod stanice (vychozi umisteni, viz README -> Konfigurace)
local ENTRANCE = vector3(290.00, -2343.00, 9.55)

if ENABLE_BLIP then
    CreateThread(function()
        local blip = AddBlipForCoord(ENTRANCE.x, ENTRANCE.y, ENTRANCE.z)
        SetBlipSprite(blip, 60)          -- policejni stanice
        SetBlipDisplay(blip, 4)
        SetBlipScale(blip, 0.85)
        SetBlipColour(blip, 29)
        SetBlipAsShortRange(blip, true)
        BeginTextCommandSetBlipName('STRING')
        AddTextComponentSubstringPlayerName('LSPD')
        EndTextCommandSetBlipName(blip)
    end)
end
