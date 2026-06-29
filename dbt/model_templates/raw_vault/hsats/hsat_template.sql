{{
    config(
        materialized='incremental',
        distributed_by='<distributed_by>',
        on_schema_change='sync_all_columns',
        apply_source_filter=true,
    )
}}
  
{%- set yaml_metadata -%}
source_model: <source_model>
src_pk: <src_pk>
src_hashdiff: <src_hashdiff>
src_payload: <src_payload>
src_eff: <src_eff>
src_ldts: <src_ldts>
src_source: <src_source>
{%- endset -%}
  
{% set metadata_dict = fromyaml(yaml_metadata) %}
  
{{ etl_sat(src_pk=metadata_dict["src_pk"],
                   src_hashdiff=metadata_dict["src_hashdiff"],
                   src_payload=metadata_dict["src_payload"],
                   src_eff=metadata_dict["src_eff"],
                   src_ldts=metadata_dict["src_ldts"],
                   src_source=metadata_dict["src_source"],
                   source_model=metadata_dict["source_model"],
                   batch_target_tbl=var('batch_target_tbl', '<batch_target_tbl>'),
                   batch_status=var('batch_status', 'START'),
                   batch_load_date=var('batch_load_date', run_started_at.strftime('%Y-%m-%d %H:%M:%S'))           
  ) }}