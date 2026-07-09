{{ config(materialized='view') }}
    
   WITH
      batch_for_load as (
   SELECT DISTINCT ON (bl.batch_id, bl.load_date, bl.batch_target_tbl)
       bl.batch_id
      ,bl.load_date as batch_load_date
      ,UPPER(bl.batch_target_tbl) as batch_target_tbl
      ,UPPER(bl.batch_status) as batch_status
   FROM {{ source('raw_stg', 'tech_batches') }} b
      JOIN {{ source('raw_stg', 'tech_batches_log') }} bl
         ON b.batch_id = bl.batch_id
   WHERE
      UPPER(bl.batch_status) = 'START'
      AND UPPER(b.table_name) = UPPER('[[ table_name ]]')
      AND b.load_date::timestamp >
      {% if var('calculation_date', none) is not none %}
            '{{ var('calculation_date') }}'::timestamp
      {% else %}
            NOW()::timestamp
      {% endif %}
      - interval '7 day'
   )
   
   SELECT
     src.*
    ,b.batch_load_date
    ,b.batch_target_tbl
    ,b.batch_status
   FROM {{ source('raw_stg', '[[ table_name ]]') }} src
      JOIN batch_for_load b
         ON src.batch_id = b.batch_id