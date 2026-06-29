import yaml
import pandas as pd

def gen_raw_stage_model(
        stg_table_name,
        save_path='',
        template_path='dbt/model_templates/raw_stage/raw_stage_template.sql'
        ):
    stg_table_name = stg_table_name.lower()
    with open(template_path, 'r') as t:
        model = t.read()
    model = model.replace('<table_name>', stg_table_name)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def gen_stage_model(
        raw_stage_model_name, hash_keys,
        save_path='',
        template_path='dbt/model_templates/stage/stage_template.sql'
        ):
    with open(template_path, 'r') as t:
        model = t.read()
    model = model.replace('<source_model>', raw_stage_model_name)

    hashed_columns = ''
    for hash_key_name, attrs in hash_keys.items():
        hashed_columns += f'\n  {hash_key_name}'
        if 'prop_hash_key' in hash_key_name:
            hashed_columns += '\n    is_hashdiff: true'
        hashed_columns += '\n    columns:'
        for attr in attrs:
            hashed_columns += f'\n    - "!{attr}"'
            hashed_columns += f'\n    - {attr}'

    model = model.replace('<hashed_columns_in>', hashed_columns)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def gen_hub_model(
        source_model, distributed_by, src_pk, src_nk, src_ldts, src_source, batch_target_tbl, 
        save_path='', template_path='dbt/model_templates/raw_vault/hubs/hub_template.sql'
        ):
    with open(template_path, 'r') as t:
        model = t.read()
    
    src_nk_str = ''
    for attr in src_nk:
        src_nk_str += f'\n  - {attr}'

    map_replace = {
        '<distributed_by>': distributed_by,
        '<source_model>': source_model,
        '<src_pk>': src_pk,
        '<src_nk>': src_nk_str,
        '<src_ldts>': src_ldts,
        '<src_source>': src_source,
        '<batch_target_tbl>': batch_target_tbl
    }


    for placeholder, value in map_replace.items():
        model = model.replace(placeholder, value)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def gen_hsat_model(
        source_model, distributed_by, src_pk, src_payload, src_ldts, src_source, batch_target_tbl,
        src_hashdiff, src_eff,
        save_path='', template_path='dbt/model_templates/raw_vault/hsats/hsat_template.sql'
        ):
    with open(template_path, 'r') as t:
        model = t.read()
    
    src_payload_str = ''
    for attr in src_payload:
        src_payload_str += f'\n  - {attr}'

    map_replace = {
        '<distributed_by>': distributed_by,
        '<source_model>': source_model,
        '<src_hashdiff>': src_hashdiff,
        '<src_pk>': src_pk,
        '<src_payload>': src_payload_str,
        '<src_eff>': src_eff,
        '<src_ldts>': src_ldts,
        '<src_source>': src_source,
        '<batch_target_tbl>': batch_target_tbl
    }

    for placeholder, value in map_replace.items():
        model = model.replace(placeholder, value)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def gen_mart_model(
        source_model_hub, source_model_hsat, distributed_by, src_pk, src_nk, src_payload, unique_key, src_eff,
        save_path='', template_path='dbt/model_templates/base_dm/mart_from_file_template.sql'
        ):
    with open(template_path, 'r') as t:
        model = t.read()

    src_nk_str = ''
    for attr in src_nk:
        src_nk_str += f'\n    h.{attr},'
    src_payload_str = ''
    for attr in src_payload:
        src_payload_str += f'\n    s.{attr},'

    map_replace = {
        '<distributed_by>': distributed_by,
        '<source_model_hub>': source_model_hub,
        '<source_model_hsat>': source_model_hsat,
        '<src_pk>': src_pk,
        '<src_payload>': src_payload_str,
        '<src_eff>': src_eff,
        '<unique_key>': unique_key,
        '<src_nk>': src_nk_str
    }

    for placeholder, value in map_replace.items():
        model = model.replace(placeholder, value)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def gen_export_part2ch_model(
        tgt_table_name, source_model, partitioning_key_date,
        save_path='', template_path='dbt/model_templates/export/export_part2ch_template.sql'
        ):
    with open(template_path, 'r') as t:
        model = t.read()

    map_replace = {
        '<tgt_table_name>': tgt_table_name,
        '<source_model>': source_model,
        '<partitioning_key_date>': partitioning_key_date
    }

    for placeholder, value in map_replace.items():
        model = model.replace(placeholder, value)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(model)

    return model

def create_yaml_spec(
        attr_desc_path,
        save_path_yml,
        model_name="",
        model_description="",
        to_append=[], 
        to_exclude=[]):
    df = pd.read_csv(attr_desc_path) 
    columns = df[['name', 'description']].to_dict(orient='records')

    column_dict = {col['name']: col['description'] for col in columns}

    for name, description in to_append:
        column_dict[name] = description
    
    for name, _ in to_exclude:
        if name in column_dict:
            del column_dict[name]

    final_columns = [{'name': name, 'description': desc} for name, desc in column_dict.items()]

    yaml_data = {
        'version': 1,
        'models': [
            {
                'name': model_name,
                'description': model_description,
                'columns': final_columns
            }
        ]
    }
    yaml_data = dict(sorted(yaml_data.items(), key=lambda item: item[0], reverse=True))

    with open(save_path_yml, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    with open("dbt/dbt_config_from_file.yaml", "r", encoding='utf-8') as s:
        dbt_config = yaml.safe_load(s)

    gen_raw_stage_model(
        stg_table_name=dbt_config['stg_table_name'],
        save_path=f'dbt/models/{dbt_config['raw_stage']}.sql'
        )
    
    gen_stage_model(
        raw_stage_model_name=dbt_config['raw_stage'], 
        hash_keys=dbt_config['hash_keys'],
        save_path=f'dbt/models/{dbt_config['stage']}.sql'
        )
    
    hub_model_name = 'hub_voice_tech_services'
    gen_hub_model(
        distributed_by=dbt_config['raw_vault']['hubs'][hub_model_name]['distributed_by'],
        source_model=dbt_config['stage'],
        src_pk=dbt_config['raw_vault']['hubs'][hub_model_name]['src_pk'],
        src_nk=dbt_config['raw_vault']['hubs'][hub_model_name]['src_nk'],
        src_ldts=dbt_config['raw_vault']['hubs'][hub_model_name]['src_ldts'],
        src_source=dbt_config['raw_vault']['hubs'][hub_model_name]['src_source'],
        batch_target_tbl=dbt_config['raw_vault']['hubs'][hub_model_name]['batch_target_tbl'],
        save_path=f'dbt/models/{hub_model_name}.sql'
    )

    hsat_model_name = 'hsat_voice_tech_services'
    gen_hsat_model(
        distributed_by=dbt_config['raw_vault']['hsats'][hsat_model_name]['distributed_by'],
        source_model=dbt_config['stage'],
        src_pk=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_pk'],
        src_payload=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_payload'],
        src_ldts=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_ldts'],
        src_source=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_source'],
        batch_target_tbl=dbt_config['raw_vault']['hsats'][hsat_model_name]['batch_target_tbl'],
        src_hashdiff=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_hashdiff'],
        src_eff=dbt_config['raw_vault']['hsats'][hsat_model_name]['src_eff'],
        save_path=f'dbt/models/{hsat_model_name}.sql'
    )

    mart_model_name = 'mart_voice_tech_services'
    gen_mart_model(
        distributed_by=dbt_config['base_dm'][mart_model_name]['distributed_by'],
        source_model_hub=dbt_config['base_dm'][mart_model_name]['source_model_hub'],
        source_model_hsat=dbt_config['base_dm'][mart_model_name]['source_model_hsat'],
        src_pk=dbt_config['base_dm'][mart_model_name]['src_pk'],
        src_payload=dbt_config['base_dm'][mart_model_name]['src_payload'],
        unique_key=dbt_config['base_dm'][mart_model_name]['unique_key'],
        src_nk=dbt_config['base_dm'][mart_model_name]['src_nk'],
        src_eff=dbt_config['base_dm'][mart_model_name]['src_eff'],
        save_path=f'dbt/models/{mart_model_name}.sql'
    )

    gen_export_part2ch_model(
        tgt_table_name=dbt_config['export_part2ch']['tgt_table_name'],
        source_model=dbt_config['export_part2ch']['source_model'],
        partitioning_key_date=dbt_config['export_part2ch']['partitioning_key_date'],
        save_path=f'dbt/models/export_part2ch_{dbt_config['export_part2ch']['tgt_table_name']}.sql'
    )