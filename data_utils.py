import yaml
import re
from datetime import datetime
from pathlib import Path
import chardet

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *

class DataFrameFromFile:
    def __init__(self, samples_dir='stream/samples', sep=';', sheetname="Лист1"):
        super().__init__()

        samples_dir = Path(samples_dir)
        filepath = next((x for x in samples_dir.iterdir() if x.is_file()), None)
        self.ext = filepath.suffix.lower()

        with open(filepath, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            self.encoding = result['encoding']

        if not self.encoding:
            self.encoding = 'utf-8'

        if self.ext == '.csv':
            self.pd = pd.read_csv(filepath, sep=sep, encoding=self.encoding, low_memory=False)
        elif self.ext == '.xlsx':
            self.pd = pd.read_excel(filepath, sheet_name=sheetname)
        else:
            raise ValueError(f"Unsupported file extension: {self.ext}")

    def get_attrs():
        pass
    

def get_duplicates_by_key(df, key: list, show_counts=False):
    duplicate_keys = df.groupby(key).size().reset_index(name='count')
    duplicate_keys = duplicate_keys[duplicate_keys['count'] > 1].sort_values("count", ascending=False)
    if show_counts:
        print(duplicate_keys.head(10))
    return duplicate_keys[key]
    
def get_max_attr_lengths(df) -> dict:
    lengths = df.astype(str).apply(lambda col: col.str.len().max())
    return lengths.to_dict()

def create_yaml_spec_from_xlsx(xlsx_file_path):
    df = pd.read_excel(xlsx_file_path)
    columns = df[['name', 'description']].to_dict(orient='records')

    yaml_data = {'columns': columns}

    with open('raw_schema.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)

def get_hsat_hub_hashdiff_cols_dbt_spec(xlsx_file_path, pk_to_exclude=['interaction_id', 'scenario_id', 'scenario_type']):
    df = pd.read_excel(xlsx_file_path)
    column_names = df['name'].tolist()
    # exclude tech cols
    pk_to_exclude.extend(['p_date', 'load_date', 'batch_id', 'doc_id', 'source'])
    column_names = [col for col in column_names if col not in pk_to_exclude]
    
    yaml_data = {'columns': column_names}
    
    with open('hsat_hashdiff_cols.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)

def create_yaml_spec_hub(xlsx_file_path, pk=['interaction_id', 'scenario_id', 'scenario_type', 'msisdn', 'bulk_cancellated_msisdn', 'new_iccid', 'service_code', 'equip_operation', 'action']):
    df = pd.read_excel(xlsx_file_path)
    columns = df[['name', 'description']].to_dict(orient='records')
    pk.extend(['load_date', 'source'])
    filtered_columns = [col for col in columns if col['name'] in pk]

    yaml_data = {'columns': filtered_columns}

    with open('hub_schema.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)




def treat_as_string(col_name):

    indicators = ['msisdn', 'phone', 'tel', 'mobile', 'cell', 'id', 'acc', 'number']
    col_name_lower = col_name.lower()
    return any(indicator in col_name_lower for indicator in indicators)

def is_timestamp_column(sample_values):

    if len(sample_values) == 0:
        return False
    
    timestamp_patterns = [
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?',
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?',
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}'
    ]
    
    timestamp_count = 0
    total_count = len(sample_values)
    for value in sample_values:
        str_value = str(value)
        for pattern in timestamp_patterns:
            if re.match(pattern, str_value):
                timestamp_count += 1
                break

    return (timestamp_count / total_count) > 0.7 if total_count > 0 else False

def is_boolean_column(sample_values):
    if len(sample_values) == 0:
        return False
    str_values = set(str(val).strip().lower() for val in sample_values)
    boolean_like_values = {'0', '1', 'true', 'false', 'yes', 'no', 'y', 'n', ''}
    
    return str_values.issubset(boolean_like_values)

def is_integer_column(sample_values):
    if len(sample_values) == 0:
        return False
    
    try:
        for value in sample_values:
            if pd.isna(value) or str(value).strip() == '':
                continue
            int(str(value))
        return True
    except (ValueError, TypeError):
        return False

def get_integer_range(sample_values):
    if len(sample_values) == 0:
        return None, None
    try:
        int_values = []
        for value in sample_values:
            if pd.isna(value) or str(value).strip() == '':
                continue
            int_values.append(int(str(value)))
        
        if int_values:
            return min(int_values), max(int_values)
        else:
            return None, None
    except (ValueError, TypeError):
        return None, None

def infer_dtype(col_name, sample_values):
    if treat_as_string(col_name):
        return 'string'
    
    if is_timestamp_column(sample_values):
        return 'timestamp'
    
    if is_boolean_column(sample_values):
        return 'tinyint'
    
    if is_integer_column(sample_values):
        min_val, max_val = get_integer_range(sample_values)
        if min_val is not None and max_val is not None:
            abs_max = max(abs(min_val), abs(max_val))
            if abs_max <= 127:
                return 'tinyint'
            elif abs_max <= 32767:
                return 'smallint'
            elif abs_max <= 2147483647:
                return 'int'
            else:
                return 'bigint'
        else:
            return 'bigint'
    
    if len(sample_values) > 0:
        try:
            for value in sample_values:
                if pd.isna(value) or str(value).strip() == '':
                    continue
                val_str = str(value).replace(',', '.')
                float(val_str)
            return 'double'
        except (ValueError, TypeError):
            pass
    
    return 'string'

def mask_sensitive_info(sample):

    phone_pattern = r'^\d{11}$'
    if re.match(phone_pattern, sample):
        masked_number = sample[:-3] + '***'
        return masked_number
    else:
        return sample

def normalize(col):
    cleaned = re.sub(r'[\r\n\t\s\u00A0]+', '_', col.strip().upper())
    return cleaned