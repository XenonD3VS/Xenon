fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'xenon_fuel'
author 'XenonD3VS'
description 'Advanced Fuel & Gas Station System – palivo, tankování, vlastnictví benzinek, zaměstnanci a rozvoz paliva'
version '1.0.0'

dependencies {
    'es_extended',
    'oxmysql',
    'ox_lib',
    'ox_target',
    'ox_inventory',
}

shared_scripts {
    '@ox_lib/init.lua',
    'shared/config.lua',
    'shared/config_vehicles.lua',
    'shared/config_stations.lua',
    'shared/locale.lua',
    'shared/utils.lua',
}

client_scripts {
    'bridge/esx/client.lua',
    'client/main.lua',
    'client/fuel.lua',
    'client/stations.lua',
    'client/refueling.lua',
    'client/management.lua',
    'client/deliveries.lua',
    'client/targets.lua',
}

server_scripts {
    '@oxmysql/lib/MySQL.lua',
    'bridge/esx/server.lua',
    'server/core.lua',
    'server/database.lua',
    'server/fuel.lua',
    'server/transactions.lua',
    'server/stations.lua',
    'server/employees.lua',
    'server/ownership.lua',
    'server/refueling.lua',
    'server/deliveries.lua',
    'server/management.lua',
    'server/commands.lua',
    'server/main.lua',
}

ui_page 'web/index.html'

files {
    'web/index.html',
    'web/style.css',
    'web/app.js',
    'web/icons.js',
    'web/fonts/*.woff2',
    'locales/*.json',
}
