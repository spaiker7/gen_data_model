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
    
    with open("confl/pages_config.yaml", "r", encoding='utf-8') as s:
        pages_config = yaml.safe_load(s)
    with open("db_types_aliases.yaml", "r") as s:
        db_aliases = yaml.safe_load(s)
    with open("dbt/dbt_config_from_file.yaml", "r") as d:
        dbt_config = yaml.safe_load(d)

    
    attrs = []

    df = DataFrameFromFile('src/sample/')
    cols = df.pd.columns.tolist()

    if any(Path('src/mapping/')):
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
            row = mapping.loc[mapping['src_name'] == src_col_name].iloc[0]
            tgt_col_name, _, description = row
        attrs.append((normalize_col_name(tgt_col_name), description, src_col_name, dtype, example)) 

    ##### HADOOP STG ######
    hdp_attrs = []
    hdp_tech_attrs = [
        ("source", "Источник данных", "string", "", "", ""),
        ("doc_id", "Идентификатор загруженного документа", "string", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
        ("batch_id", "Идентификатор пачки, в которой загружен документ", "string", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
        ("load_date", "Дата и время создания записи", "timestamp", "datetime.now()", "", "2026-06-07 23:02:15"),
        ("p_date", "Дата создания записи", "timestamp", "v_calc_date (airflow date)", "PARTITION BY", "2026-06-07"),
    ]
    for (tgt_col_name, description, src_col_name, dtype, example) in attrs:
        hdp_attrs.append((tgt_col_name, description, db_aliases[dtype]["hadoop"], f"&lt;*{df.ext}&gt;/{src_col_name}", "", example))
    hdp_attrs.extend(hdp_tech_attrs)

    template_stg = open("stream/jnj_templates/stg_hdp_page_jnj_template.html", "r", encoding="utf-8").read()
    # add message example to page
    if df.ext in ['.json', '.xml']:
        with open(df.filepath, 'r') as f:
            sample_text = f.read()
        if df.ext == '.json':
            sample_language = 'java'
    
    body = Template(template_stg).render(
        schema_name=pages_config["stg_hadoop"]["schema_name"], 
        table_name=pages_config["stg_hadoop"]["table_name"], 
        table_desc=pages_config["stg_hadoop"]["table_desc"], 
        system_source=pages_config["stg_hadoop"]["system_source"],
        update_schedule=pages_config["stg_hadoop"]["update_schedule"],
        history_depth=pages_config["stg_hadoop"]["history_depth"],
        attrs=hdp_attrs,
        sample_language=sample_language,
        sample_ext=df.ext,
        sample_text=sample_text
    )
        
    confluence.create_page(
        space=pages_config["space_key"],
        title=pages_config["stg_hadoop"]["title"],
        body=body,
        parent_id=pages_config["stg_hadoop"]["parent_id_page"],
        representation='storage'
    )

    ##### GREENPLUM STG ######
    gp_attrs = []
    gp_tech_attrs = [
        ("source", "Источник данных", "text", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.source", "", f"{pages_config["stg_hadoop"]["source_name"]}"),
        ("doc_id", "Идентификатор загруженного документа", "text", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.doc_id", "", "17816007320693"),
        ("batch_id", "Идентификатор пачки, в которой загружен документ", "text", f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.batch_id", "", "17816007320693"),
        ("load_date", "Дата и время создания записи", "timestamp", "datetime.now()", "", "2026-06-07 23:02:15"),
    ]
    for (tgt_col_name, description, src_col_name, dtype, example) in attrs:
        gp_attrs.append((tgt_col_name, description, db_aliases[dtype]["greenplum"], f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.{tgt_col_name}", "", example))
    gp_attrs.extend(gp_tech_attrs)

    raw_stage_model_name = dbt_config['raw_stage_model_name']
    with open(f'dbt/models/{raw_stage_model_name}.sql', 'r') as f:
        raw_stage_model = f.read()
    
    create_yaml_spec(
        attr_desc_path='src/mapping/attrs.csv',
        save_path_yml=f'dbt/spec/{raw_stage_model_name}.yml',
        model_name=raw_stage_model_name,
        model_description="Сырые данные из источника за последние 7 дней",
        to_append=[attr[0] for attr in gp_tech_attrs], 
        to_exclude=[])
    raw_stage_model_spec_name = f'dbt/spec/{raw_stage_model_name}.yml'
    with open(raw_stage_model_spec_name, 'r') as f:
        raw_stage_model_spec = f.read()

    stage_model_name = dbt_config['stage_model_name']
    with open(f'dbt/models/{stage_model_name}.sql', 'r') as f:
        stage_model = f.read()
    
    create_yaml_spec(
        attr_desc_path='src/mapping/attrs.csv',
        save_path_yml=f'dbt/spec/{stage_model_name}.yml',
        model_name=stage_model_name,
        model_description="Сырые данные из источника за последние 7 дней",
        to_append=[attr[0] for attr in gp_tech_attrs], 
        to_exclude=[])
    stage_model_spec_name = f'dbt/spec/{stage_model_name}.yml'
    with open(stage_model_spec_name, 'r') as f:
        stage_model_spec = f.read()

    template_stg = open("stream/jnj_templates/stg_gp_page_jnj_template.html", "r", encoding="utf-8").read()  
    body = Template(template_stg).render(
        schema_name=pages_config["stg_gp"]["schema_name"], 
        table_name=pages_config["stg_gp"]["table_name"], 
        table_desc=pages_config["stg_gp"]["table_desc"], 
        system_source=pages_config["stg_gp"]["system_source"],
        update_schedule=pages_config["stg_gp"]["update_schedule"],
        history_depth=pages_config["stg_gp"]["history_depth"],
        attrs=gp_attrs,
        raw_stage_model_name=raw_stage_model_name,
        raw_stage_model=raw_stage_model,
        raw_stage_model_spec_name=raw_stage_model_spec_name,
        raw_stage_model_spec=raw_stage_model_spec,
        stage_model_name=stage_model_name,
        stage_model=stage_model,
        stage_model_spec_name=raw_stage_model_spec_name,
        stage_model_spec=raw_stage_model_spec
    )      
    confluence.create_page(
        space=pages_config["space_key"],
        title=pages_config["stg_gp"]["title"],
        body=body,
        parent_id=pages_config["stg_gp"]["parent_id_page"],
        representation='storage'
    )


    # hash_keys = {
    #     "mts_service_sw_hash_key": ['interaction_id', 'scenario_id', 'msisdn'],
    #     "mts_service_sw_prop_hash_key": ['interaction_started_dt', 'scenario_reason']
    # }

if __name__ == "__main__":
    main()
