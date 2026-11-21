--[[
    xenon_fuel – databáze (oxmysql)
    Tabulky se vytvoří automaticky při startu. Stejná struktura je v install.sql.
]]

Database = {}

local schema = {
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_vehicles` (
        `plate` VARCHAR(12) NOT NULL,
        `fuel` DECIMAL(5,2) NOT NULL DEFAULT 100.00,
        `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`plate`),
        KEY `idx_updated` (`updated_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_stations` (
        `id` VARCHAR(64) NOT NULL,
        `owner` VARCHAR(64) DEFAULT NULL,
        `owner_name` VARCHAR(100) DEFAULT NULL,
        `label` VARCHAR(64) DEFAULT NULL,
        `balance` BIGINT NOT NULL DEFAULT 0,
        `is_open` TINYINT(1) NOT NULL DEFAULT 1,
        `prices` LONGTEXT DEFAULT NULL,
        `total_revenue` BIGINT NOT NULL DEFAULT 0,
        `total_costs` BIGINT NOT NULL DEFAULT 0,
        `customers` INT UNSIGNED NOT NULL DEFAULT 0,
        `liters_sold` DECIMAL(14,2) NOT NULL DEFAULT 0,
        `purchase_price` INT UNSIGNED NOT NULL DEFAULT 0,
        `purchased_at` INT UNSIGNED DEFAULT NULL,
        `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_owner` (`owner`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_stock` (
        `station_id` VARCHAR(64) NOT NULL,
        `fuel_type` VARCHAR(32) NOT NULL,
        `liters` DECIMAL(12,2) NOT NULL DEFAULT 0,
        PRIMARY KEY (`station_id`, `fuel_type`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_employees` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `station_id` VARCHAR(64) NOT NULL,
        `identifier` VARCHAR(64) NOT NULL,
        `name` VARCHAR(100) NOT NULL,
        `rank` VARCHAR(32) NOT NULL,
        `permissions` LONGTEXT DEFAULT NULL,
        `seconds_worked` INT UNSIGNED NOT NULL DEFAULT 0,
        `total_paid` BIGINT NOT NULL DEFAULT 0,
        `hired_at` INT UNSIGNED NOT NULL,
        `last_shift` INT UNSIGNED DEFAULT NULL,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uniq_station_identifier` (`station_id`, `identifier`),
        KEY `idx_identifier` (`identifier`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_shifts` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `station_id` VARCHAR(64) NOT NULL,
        `identifier` VARCHAR(64) NOT NULL,
        `started_at` INT UNSIGNED NOT NULL,
        `ended_at` INT UNSIGNED NOT NULL,
        `seconds` INT UNSIGNED NOT NULL DEFAULT 0,
        `earned` INT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (`id`),
        KEY `idx_station_started` (`station_id`, `started_at`),
        KEY `idx_identifier` (`identifier`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_finance` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `station_id` VARCHAR(64) NOT NULL,
        `type` VARCHAR(24) NOT NULL,
        `amount` BIGINT NOT NULL,
        `balance` BIGINT NOT NULL,
        `actor` VARCHAR(64) DEFAULT NULL,
        `actor_name` VARCHAR(100) DEFAULT NULL,
        `note` VARCHAR(255) DEFAULT NULL,
        `created_at` INT UNSIGNED NOT NULL,
        PRIMARY KEY (`id`),
        KEY `idx_station_created` (`station_id`, `created_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_refuels` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `receipt` VARCHAR(20) NOT NULL,
        `identifier` VARCHAR(64) NOT NULL,
        `player_name` VARCHAR(100) DEFAULT NULL,
        `station_id` VARCHAR(64) NOT NULL,
        `station_label` VARCHAR(64) NOT NULL,
        `plate` VARCHAR(12) DEFAULT NULL,
        `fuel_type` VARCHAR(32) NOT NULL,
        `liters` DECIMAL(10,2) NOT NULL,
        `price_per_liter` DECIMAL(10,2) NOT NULL,
        `total` INT UNSIGNED NOT NULL,
        `payment_method` VARCHAR(16) NOT NULL,
        `created_at` INT UNSIGNED NOT NULL,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uniq_receipt` (`receipt`),
        KEY `idx_identifier_created` (`identifier`, `created_at`),
        KEY `idx_station_created` (`station_id`, `created_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_orders` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `station_id` VARCHAR(64) NOT NULL,
        `fuel_type` VARCHAR(32) NOT NULL,
        `liters` INT UNSIGNED NOT NULL,
        `cost` INT UNSIGNED NOT NULL,
        `reward` INT UNSIGNED NOT NULL DEFAULT 0,
        `method` VARCHAR(16) NOT NULL,
        `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
        `ordered_by` VARCHAR(64) DEFAULT NULL,
        `ordered_by_name` VARCHAR(100) DEFAULT NULL,
        `driver` VARCHAR(64) DEFAULT NULL,
        `driver_name` VARCHAR(100) DEFAULT NULL,
        `created_at` INT UNSIGNED NOT NULL,
        `deliver_at` INT UNSIGNED NOT NULL DEFAULT 0,
        `delivered_at` INT UNSIGNED DEFAULT NULL,
        PRIMARY KEY (`id`),
        KEY `idx_status` (`status`),
        KEY `idx_station_status` (`station_id`, `status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
    [[
    CREATE TABLE IF NOT EXISTS `xenon_fuel_admin_log` (
        `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
        `admin` VARCHAR(64) DEFAULT NULL,
        `admin_name` VARCHAR(100) DEFAULT NULL,
        `action` VARCHAR(32) NOT NULL,
        `target` VARCHAR(100) DEFAULT NULL,
        `details` VARCHAR(255) DEFAULT NULL,
        `created_at` INT UNSIGNED NOT NULL,
        PRIMARY KEY (`id`),
        KEY `idx_created` (`created_at`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ]],
}

function Database.Init()
    for _, query in ipairs(schema) do
        MySQL.query.await(query)
    end

    local purgeDays = Config.Fuel.Persistence.PurgeAfterDays
    if Config.Features.PersistFuel and purgeDays and purgeDays > 0 then
        local removed = MySQL.update.await(
            'DELETE FROM `xenon_fuel_vehicles` WHERE `updated_at` < (NOW() - INTERVAL ? DAY)',
            { purgeDays }
        )
        if removed and removed > 0 then
            Utils.Debug(('Odstraněno %d starých záznamů paliva'):format(removed))
        end
    end
end
