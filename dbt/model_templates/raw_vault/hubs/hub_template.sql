{{
    config(
        materialized='incremental',
        distributed_by='voice_tech_hash_key',
        on_schema_change='sync_all_columns',
        apply_source_filter=true,
    )
}}
  
{%- set yaml_metadata -%}
source_model: v_voice_tech_services_tt_hub_hsat
src_pk: voice_tech_hash_key
src_nk:
   - msisdn
   - service_name
   - validfrom
src_ldts: load_date
src_source: source
{%- endset -%}
  
{% set metadata_dict = fromyaml(yaml_metadata) %}
  
{{
etl_sat(
       src_pk=metadata_dict["src_pk"],
       src_ldts=metadata_dict["src_ldts"],
       src_nk=metadata_dict["src_nk"],
       src_source=metadata_dict["src_source"],
       source_model=metadata_dict["source_model"],
       batch_target_tbl=var('batch_target_tbl', 'dv.hub_voice_tech_services'),
       batch_status=var('batch_status', 'START'),
       batch_load_date=var('batch_load_date', run_started_at.strftime('%Y-%m-%d %H:%M:%S'))
)
}}