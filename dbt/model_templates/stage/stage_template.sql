{{ config(materialized='view') }}
 
{%- set yaml_metadata -%}
source_model: <source_model>
hashed_columns: <hashed_columns_in>

{%- endset -%}
 
{% set metadata_dict = fromyaml(yaml_metadata) %}
 
with staging as (
  {{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
)
 
select *
from staging