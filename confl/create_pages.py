import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv
from atlassian import Confluence
from jinja2 import Template
from datetime import datetime
import pandas as pd

from data_utils import DataFrameFromFile, infer_dtype, mask_sensitive_info, normalize


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
    
    with open("gen_stream_model/config.yaml", "r", encoding='utf-8') as s:
        stream_config = yaml.safe_load(s)
    
    attrs = []

    df = DataFrameFromFile('stream/samples')
    cols = df.pd.columns.tolist()

    for col_name in cols:
        series = df.pd[col_name].dropna()
        if pd.api.types.is_numeric_dtype(series):
            if (series % 1 == 0).all():
                series = series.astype(int)
        series = series.astype(str)
        hadoop_dtype = infer_dtype(col_name, series)
        if not series.empty:
            example = mask_sensitive_info(series.iloc[0])
        else:
            example = ''
        attrs.append((normalize(col_name), col_name, hadoop_dtype, f"&lt;*{df.ext}&gt;/{col_name}", example))

    ##### HADOOP STG ######

    tech_attrs = [
        ("source", "Источник данных", "STRING", "", ""),
        ("doc_id", "Идентификатор загруженного документа", "STRING", "tech_stg.xml_archive", "17816007320693"),
        ("batch_id", "Идентификатор пачки, в которой загружен документ", "STRING", "tech_stg.xml_archive", "17816007320693"),
        ("load_date", "Дата и время создания записи", "TIMESTAMP", "datetime.now()", "2026-06-16 23:02:15"),
        ("p_date", "Дата создания записи (ключ партицирования)", "TIMESTAMP", "v_calc_date (airflow date)", "2026-06-07"),
    ]
    attrs.extend(tech_attrs)

    template_stg = open("stream/stg_page_jnj_template.html", "r", encoding="utf-8").read()
    body = Template(template_stg).render(
        schema_name="SW_STG",
        table_name="MTS_SERVICE_SW_TSRETAIL",
        table_desc=stream_config["stg_hadoop"]["table_desc"], 
        system_source=stream_config["stg_hadoop"]["system_source"],
        update_schedule=stream_config["stg_hadoop"]["update_schedule"],
        history_depth=stream_config["stg_hadoop"]["history_depth"],
        attrs=attrs
    )
    confluence.create_page(
        space=stream_config["space_key"],
        title=stream_config["stg_hadoop"]["title"],
        body=body,
        parent_id="2182845903",
        representation='storage'
    )

    ##### GREENPLUM STG ######


if __name__ == "__main__":
    main()

# 

    # page = confluence.get_page_by_id(
    #         page_id='2379581623', 
    #         # 2422789695 2422783316
    #         expand='body.storage,version,space,ancestors,title'
    #     )
    # from bs4 import BeautifulSoup
    # html_content = page["body"]["storage"]["value"]
    # soup_formatted = BeautifulSoup(html_content, 'html.parser')
    # for tr in soup_formatted.find_all('tr'):
    #     tr.append('\n')

    # with open('test.html', 'w', encoding='utf-8') as f:
    #     f.write(str(soup_formatted))


