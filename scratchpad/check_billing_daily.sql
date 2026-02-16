-- Check billing_daily table for the current billing period (Jan 16 - Feb 15)

SELECT
    date,
    import_off_kwh,
    import_peak_kwh,
    export_off_kwh,
    export_peak_kwh,
    solar_generation_kwh,
    load_consumption_kwh,
    bill_final_rs_to_date,
    surplus_deficit_flag
FROM billing_daily
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
    AND date >= '2026-01-16'
    AND date <= '2026-02-15'
ORDER BY date;

-- Count how many days we have
SELECT COUNT(*) as total_days
FROM billing_daily
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
    AND date >= '2026-01-16'
    AND date <= '2026-02-15';

-- Check billing_month table
SELECT
    billing_month,
    year,
    period_start,
    period_end,
    import_off_kwh,
    import_peak_kwh,
    export_off_kwh,
    export_peak_kwh,
    bill_final_rs
FROM billing_month
WHERE site_id = '271edc3f-f8e8-4aac-acae-78ffd8bf4643'
    AND period_start = '2026-01-16';
