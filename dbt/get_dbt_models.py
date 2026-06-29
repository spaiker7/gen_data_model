import yaml
import pandas as pd

def gen_raw_stage_model(
        stg_table_name,
        save_path='',
        template_path='model_templates/raw_stage/raw_stage_template.sql'
        ):
    stg_table_name = stg_table_name.lower()
    with open(template_path, 'r') as t:
        model = t.read()
    model = model.replace('<table_name>', stg_table_name)

    if save_path:
        with open(save_path, 'w') as f:
            f.write(save_path)

    return model

def gen_stage_model(
        raw_stage_model_name, hash_keys,
        save_path='',
        template_path='model_templates/stage/stage_template.sql'
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
            f.write(save_path)

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


# if __name__ == "__main__":
#     main()
