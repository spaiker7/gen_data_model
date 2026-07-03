import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv
from atlassian import Confluence
from jinja2 import Template
import pandas as pd

from data_utils import DataFrameFromFile, infer_dtype, mask_sensitive_info, normalize_col_name
from dbt.get_dbt_models import create_yaml_spec

def load_env():
    dotenv_path = Path(__file__).parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    
    base_url = os.getenv("CONFLUENCE_BASE_URL")
    token = os.getenv("CONFLUENCE_TOKEN")
        
    return base_url, token


def main():
    base_url, token = load_env()
    
    confluence = Confluence(
        url=base_url,
        token=token,
        verify_ssl=False
    )
    
    with open("confl/pages_config_card_issuance_detailed.yaml", "r", encoding='utf-8') as s:
        pages_config = yaml.safe_load(s)
    with open("db_types_aliases.yaml", "r") as s:
        db_aliases = yaml.safe_load(s)
    with open("dbt/dbt_config_from_file_card_issuance_detailed.yaml", "r") as d:
        dbt_config = yaml.safe_load(d)

    Path('dbt/spec/').mkdir(parents=True, exist_ok=True)
    
    attrs = []

    df = DataFrameFromFile('src/sample/')
    cols = df.pd.columns.tolist()

    if any(Path('src/mapping/').iterdir()):
        mapping = DataFrameFromFile('src/mapping/').pd

    for src_col_name in cols:
        series = df.pd[src_col_name].dropna()
        if pd.api.types.is_numeric_dtype(series):
            if (series % 1 == 0).all():
                series = series.astype(int)
        series = series.astype(str)
        dtype = infer_dtype(src_col_name, series)
        if not series.empty:
            example = mask_sensitive_info(series.iloc[0])
        else:
            example = ''
        if any(mapping):
            row = mapping.loc[mapping['src_name'] == src_col_name]
            tgt_col_name, _, description = row.iloc[0]

        attrs.append((normalize_col_name(tgt_col_name), description, src_col_name, dtype, example)) 

    # ##### HADOOP STG ######
    # hdp_attrs = []
    # hdp_tech_attrs = [
    #     ("SOURCE", "Источник данных", "STRING", "", "", ""),
    #     ("DOC_ID", "Идентификатор загруженного документа", "STRING", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
    #     ("BATCH_ID", "Идентификатор пачки, в которой загружен документ", "STRING", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
    #     ("LOAD_DATE", "Дата и время создания записи", "TIMESTAMP", "datetime.now()", "", "2026-06-07 23:02:15"),
    #     ("P_DATE", "Дата создания записи", "TIMESTAMP", "v_calc_date (airflow date)", "PARTITION BY", "2026-06-07"),
    # ]
    # for (tgt_col_name, description, src_col_name, dtype, example) in attrs:
    #     hdp_attrs.append((tgt_col_name, description, db_aliases[dtype]["hadoop"].upper(), f"&lt;*{df.ext}&gt;/{src_col_name}", "", example))
    # hdp_attrs.extend(hdp_tech_attrs)

    # template_stg = open("confl/jnj_templates/stg_hdp_page_jnj_template.html", "r", encoding="utf-8").read()
    # # add message example to page
    # if df.ext in ['.json', '.xml']:
    #     with open(df.filepath, 'r') as f:
    #         sample_text = f.read()
    #     if df.ext == '.json':
    #         sample_language = 'java'
    # else:
    #     sample_language = ''
    #     sample_text = ''
    
    # body = Template(template_stg).render(
    #     schema_name=pages_config["stg_hadoop"]["schema_name"], 
    #     table_name=pages_config["stg_hadoop"]["table_name"], 
    #     table_desc=pages_config["stg_hadoop"]["table_desc"], 
    #     system_source=pages_config["stg_hadoop"]["system_source"],
    #     update_schedule=pages_config["stg_hadoop"]["update_schedule"],
    #     history_depth=pages_config["stg_hadoop"]["history_depth"],
    #     attrs=hdp_attrs,
    #     sample_language=sample_language,
    #     sample_ext=df.ext,
    #     sample_text=sample_text
    # )
        
    # confluence.create_page(
    #     space=pages_config["space_key"],
    #     title=pages_config["stg_hadoop"]["title"],
    #     body=body,
    #     parent_id=pages_config["stg_hadoop"]["parent_id_page"],
    #     representation='storage'
    # )

    ##### GREENPLUM STG ######
    gp_attrs = []
    gp_tech_attrs = [
        ("SOURCE", "Источник данных", "TEXT", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.SOURCE", "", f"{pages_config["stg_hadoop"]["source_name"]}"),
        ("DOC_ID", "Идентификатор загруженного документа", "TEXT", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.DOC_ID", "", "17816007320693"),
        ("BATCH_ID", "Идентификатор пачки, в которой загружен документ", "TEXT", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.BATCH_ID", "", "17816007320693"),
        ("LOAD_DATE", "Дата и время создания записи", "TIMESTAMP", "datetime.now()", "", "2026-06-07 23:02:15"),
    ]
    for (tgt_col_name, description, src_col_name, dtype, example) in attrs:
        gp_attrs.append((tgt_col_name, description, db_aliases[dtype]["greenplum"].upper(), f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.{tgt_col_name}".upper(), "", example))
    gp_attrs.extend(gp_tech_attrs)

    raw_stage_model_name = dbt_config['raw_stage_model_name']
    with open(f'dbt/models/{raw_stage_model_name}.sql', 'r') as f:
        raw_stage_model = f.read()

    to_append = [(attr[0].lower(), attr[1])  for attr in gp_tech_attrs]
    print(to_append)
    create_yaml_spec(
        attr_desc_path='src/mapping/',
        save_path_yml=f'dbt/spec/{raw_stage_model_name}.yml',
        model_name=raw_stage_model_name,
        model_description="Сырые данные из источника за последние 7 дней",
        to_append=to_append,
        to_exclude=[])
    raw_stage_model_spec_name = f'dbt/spec/{raw_stage_model_name}.yml'
    with open(raw_stage_model_spec_name, 'r', encoding='utf-8') as f:
        raw_stage_model_spec = f.read()

    stage_model_name = dbt_config['stage_model_name']
    with open(f'dbt/models/{stage_model_name}.sql', 'r') as f:
        stage_model = f.read()
    
    hash_attrs_for_spec = []
    for hash_key, attrs in dbt_config['hash_keys'].items():
        if 'prop_hash_key' in hash_key:
            desc = 'Хэш атрибутов свойств'
        else:
            desc = 'Хэш-ключ'
    hash_attrs_for_spec.append((hash_key, desc))

    tech_attrs_for_spec = [(attr[0].lower(), attr[1]) for attr in gp_tech_attrs]
    hash_attrs_for_spec.extend(tech_attrs_for_spec)

    create_yaml_spec(
        attr_desc_path='src/mapping/',
        save_path_yml=f'dbt/spec/{stage_model_name}.yml',
        model_name=stage_model_name,
        model_description="Сырые данные из источника за последние 7 дней",
        to_append=hash_attrs_for_spec, 
        to_exclude=[])
    stage_model_spec_name = f'dbt/spec/{stage_model_name}.yml'
    with open(stage_model_spec_name, 'r', encoding='utf-8') as f:
        stage_model_spec = f.read()

    template_stg = open("confl/jnj_templates/stg_gp_page_jnj_template.html", "r", encoding="utf-8").read()  
    body = Template(template_stg).render(
        schema_name=pages_config["stg_gp"]["schema_name"], 
        table_name=pages_config["stg_gp"]["table_name"], 
        table_desc=pages_config["stg_gp"]["table_desc"], 
        update_schedule=pages_config["stg_gp"]["update_schedule"],
        history_depth=pages_config["stg_gp"]["history_depth"],
        attrs=gp_attrs,
        raw_stage_model_name=raw_stage_model_name,
        raw_stage_model=raw_stage_model,
        raw_stage_model_spec_name=raw_stage_model_name,
        raw_stage_model_spec=raw_stage_model_spec,
        stage_model_name=stage_model_name,
        stage_model=stage_model,
        stage_model_spec_name=stage_model_name,
        stage_model_spec=stage_model_spec
    )      
    confluence.create_page(
        space=pages_config["space_key"],
        title=pages_config["stg_gp"]["title"],
        body=body,
        parent_id=pages_config["stg_gp"]["parent_id_page"],
        representation='storage'
    )

    ##### GREENPLUM RAW VAULT ######

    # for hsat_config in dbt_config['raw_vault']['hsats']:


if __name__ == "__main__":
    main()
