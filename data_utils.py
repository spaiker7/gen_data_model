import csv
import yaml
import json
import re
import logging
from pathlib import Path
import chardet
import pandas as pd
from typing import Any
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

class TabularFromFile:
    def __init__(self, path, json_parse_sep=".", sheet_name=0):
        path = Path(path)

        if path.is_dir():
            self.filepath = next((x for x in path.iterdir() if x.is_file()), None)
            if self.filepath is None:
                raise FileNotFoundError(f"No files found in {path}")
        else:
            self.filepath = path

        self.ext = self.filepath.suffix.lower()
        self.json_parse_sep = json_parse_sep
        self.sheet_name = sheet_name

        with open(self.filepath, "rb") as f:
            raw = f.read()
            self.encoding = chardet.detect(raw)["encoding"] or "utf-8"

        self.READERS = {
            ".csv": self._read_csv,
            ".xlsx": self._read_excel,
            ".xls": self._read_excel,
            ".json": self._read_json,
        }

        reader = self.READERS.get(self.ext)
        if reader is None:
            raise ValueError(f"Unsupported file extension: {self.ext}")

        self.pd = reader()

    def _detect_separator(self):
        with open(self.filepath, "r", encoding=self.encoding, newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter

    def _read_csv(self):
        return pd.read_csv(
            self.filepath,
            sep=self._detect_separator(),
            encoding=self.encoding,
            low_memory=False,
        )

    def _read_excel(self):
        return pd.read_excel(
            self.filepath,
            sheet_name=self.sheet_name,
        )

    def _read_json(self):
        with open(self.filepath, encoding=self.encoding) as f:
            data = json.load(f)

        return pd.json_normalize(
            data,
            sep=self.json_parse_sep,
        )


class TemplateGenerator:
    def __init__(
        self,       
        template_root: str | Path = "."
    ):

        self.env = Environment(
            loader=FileSystemLoader(template_root),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            variable_start_string="[[",
            variable_end_string="]]",
            block_start_string="<%",
            block_end_string="%>"
        )

    def render_template(
        self,
        template_path: str,
        context: dict[str, Any]
    ) -> str:

        template = self.env.get_template(template_path)
        return template.render(**context)
    
    def save(
        self,
        output_path: str | Path,
        content: str
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("Generated %s", output_path)
    
    def render_to_file(
        self,
        *,
        template_path: str,
        output_path: Path,
        context: dict
    ):
        content = self.render_template(template_path, context)
        self.save(output_path, content)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
        
    @staticmethod
    def _load_json(path: Path) -> list[dict[str, Any]]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
        
    @staticmethod
    def unique(*lists) -> list[str]:

        seen = set()
        result = []

        for lst in lists:
            for col in lst:
                if col not in seen:
                    seen.add(col)
                    result.append(col)

        return result  
          
def mask_sensitive_info(sample):

    phone_pattern = r'^\d{11}$'
    if re.match(phone_pattern, sample):
        masked_number = sample[:-3] + '***'
        return masked_number
    else:
        return sample

def normalize_col_name(col):
    cleaned = re.sub(r'[\r\n\t\s\u00A0]+', '_', col.strip().upper())
    return cleaned

def get_duplicates_by_key(df, key: list, show_counts=False):
    duplicate_keys = df.groupby(key).size().reset_index(name='count')
    duplicate_keys = duplicate_keys[duplicate_keys['count'] > 1].sort_values("count", ascending=False)
    if show_counts:
        print(duplicate_keys.head(10))
    return duplicate_keys[key]
    
def get_max_attr_lengths(df) -> dict:
    lengths = df.astype(str).apply(lambda col: col.str.len().max())
    return lengths.to_dict()

def is_timestamp_column(sample_values, date_as_timestamp=True):

    if len(sample_values) == 0:
        return False
    
    timestamp_patterns = [
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?',
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?',
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}'
    ]
    
    if date_as_timestamp:
        timestamp_patterns.append(r'\d{4}-\d{2}-\d{2}')
    
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

def infer_dtype(col_name, 
                sample_values,
                # treat col as string
                str_indicators = ['msisdn', 'phone', 'tel', 'mobile',
                                   'cell', 'id', 'acc', 'number']):

    
    if any(indicator in col_name.lower() for indicator in str_indicators):
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