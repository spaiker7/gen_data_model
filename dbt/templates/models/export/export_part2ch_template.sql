{{
    config(
        materialized='incremental',
        schema='dwh',
        alias='export_part2ch',
        unique_key=['table_name','part_period_name'],
        on_schema_change='ignore'
    )
}}
 
{% set curdate = var('curdate', none) %}
WITH changed_parts AS (
    SELECT
        '[[ tgt_table_name ]]' as table_name,
        to_char(m.[[ partitioning_key_date ]], 'YYYYMM') as part_period_name,
        cast(to_char(m.[[ partitioning_key_date ]], 'YYYYMM') as int4) as part_id,
        'auto' as type_load
    FROM {{ ref('[[ source_model ]]') }} m
    {% if curdate is not none %}
    WHERE m.load_date >= cast('{{ curdate }}' as timestamp)
    {% endif %}
    GROUP BY 1,2,3,4
)
 
SELECT
    cp.part_id,
    cp.table_name,
    cp.part_period_name,
    cp.type_load
FROM changed_parts cp
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ this }} 
    WHERE e.table_name = cp.table_name
      AND e.part_period_name = cp.part_period_name
)
;