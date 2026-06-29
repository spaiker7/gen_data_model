{{
    config(
        materialized='incremental',
        unique_key = ['voice_tech_hash_key'],
        distributed_by='voice_tech_hash_key',
        on_schema_change='sync_all_columns'
    )
}}
 
WITH ranked_hsat AS (
    SELECT
         
      s.voice_tech_hash_key,
      -- payload:
      s.pay_month,
      s.sale_date,
      s.source_conn,
      s.trial_valid_from,
      s.valid_to,
      s.charge_date,
      s.days_paid,
      s.payment_amount,
      s.family_members_count,
      s.source_proccessed_date,
      -- tech:
      s.load_date,
      s.source,
 
        row_number() over (
            partition by s.voice_tech_hash_key
            order by
                s.source_proccessed_date desc
        ) as rn
    FROM {{ ref('hsat_voice_tech_services') }} s
WHERE 1=1
{% if is_incremental() %}
AND s.load_date >= COALESCE( (SELECT MAX(load_date) FROM {{ this }}), '1900-01-01')
{% endif %}
)
 
SELECT
      h.voice_tech_hash_key,
      -- NK from HUB:
      h.msisdn,
      h.service_name,
      h.valid_from,
    -- payload from HSAT:
      s.pay_month,
      s.sale_date,
      s.source_conn,
      s.trial_valid_from,
      s.valid_to,
      s.charge_date,
      s.days_paid,
      s.payment_amount,
      s.family_members_count,
      s.source_proccessed_date,
      -- tech:
      s.load_date,
      s.source,
    now() as modified_date
FROM {{ ref('hub_voice_tech_services') }} h
JOIN ranked_hsat s
  ON h.voice_tech_hash_key = s.voice_tech_hash_key
WHERE s.rn = 1
;