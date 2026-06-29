import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv
from atlassian import Confluence
from jinja2 import Template
import pandas as pd

from data_utils import DataFrameFromFile, infer_dtype, mask_sensitive_info, normalize_col_name


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
    
    attrs = []

    df = DataFrameFromFile('src/')
    cols = df.pd.columns.tolist()


    for col_name in cols:
        series = df.pd[col_name].dropna()
        if pd.api.types.is_numeric_dtype(series):
            if (series % 1 == 0).all():
                series = series.astype(int)
        series = series.astype(str)
        dtype = infer_dtype(col_name, series)
        if not series.empty:
            example = mask_sensitive_info(series.iloc[0])
        else:
            example = ''
        attrs.append((col_name, dtype, example)) 

    ##### HADOOP STG ######
    hdp_attrs = []
    hdp_tech_attrs = [
        ("source", "Источник данных", "string", "", "", ""),
        ("doc_id", "Идентификатор загруженного документа", "string", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
        ("batch_id", "Идентификатор пачки, в которой загружен документ", "string", f"{pages_config["stg_hadoop"]["archive_schema_table_name"]}", "", "17816007320693"),
        ("load_date", "Дата и время создания записи", "timestamp", "datetime.now()", "", "2026-06-07 23:02:15"),
        ("p_date", "Дата создания записи", "timestamp", "v_calc_date (airflow date)", "PARTITION BY", "2026-06-07"),
    ]
    for (col_name, dtype, example) in attrs:
        hdp_attrs.append((normalize_col_name(col_name), "", db_aliases[dtype]["hadoop"], f"&lt;*{df.ext}&gt;/{col_name}", "", example))
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
    for (col_name, dtype, example) in attrs:
        gp_attrs.append((normalize_col_name(col_name), "", db_aliases[dtype]["greenplum"], f"{pages_config["stg_hadoop"]["schema_name"]}.{pages_config["stg_hadoop"]["table_name"]}.{normalize_col_name(col_name)}", "", example))
    gp_attrs.extend(gp_tech_attrs)

    template_stg = open("stream/jnj_templates/stg_gp_page_jnj_template.html", "r", encoding="utf-8").read()  
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
