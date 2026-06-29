{{
    config(
        materialized='incremental',
        unique_key = ['<unique_key>'],
        distributed_by='<distributed_by>',
        on_schema_change='sync_all_columns'
    )
}}
 
WITH ranked_hsat AS (
  SELECT
    s.<src_pk>,<src_payload>
    s.source,
    row_number() over (
            partition by s.<src_pk>
            order by s.load_date desc, s.<src_eff> desc
        ) as rn
    FROM {{ ref('<source_model_hsat>') }} s
WHERE 1=1
{% if is_incremental() %}
AND s.load_date >= COALESCE( (SELECT MAX(load_date) FROM {{ this }}), '1900-01-01')
{% endif %}
)
 
SELECT
    h.<src_pk>,<src_nk><src_payload>
    s.source,
    now() as load_date
FROM {{ ref('<source_model_hub>') }} h
JOIN ranked_hsat s
  ON h.<src_pk> = s.<src_pk>
WHERE s.rn = 1
;