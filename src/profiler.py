import pandas as pd
from typing import List, Dict, Any

from data_utils import (
    TabularFromFile,
    infer_dtype,
    mask_sensitive_info,
    normalize_col_name,
)
from src.schema_models import AttrProfile, load_mapping


def build_schema(
    sample_dir: str,
    mapping_dir: str
    ) -> List[Dict[str, Any]]:

    df = TabularFromFile(sample_dir)
    data = df.pd
    columns = data.columns.tolist()

    mapping = load_mapping(mapping_dir)

    schema = []

    for col in columns:
        series = data[col].dropna()

        # sample handling
        example = ""
        if not series.empty:
            example = mask_sensitive_info(str(series.iloc[0]))

        dtype = infer_dtype(col, series)

        if col in mapping:
            target_name = normalize_col_name(mapping[col]["name"])
            description = mapping[col]["description"]
        else:
            target_name = normalize_col_name(col)
            description = ""

        schema.append(
            AttrProfile(
                name=target_name,
                source_name=col,
                dtype=dtype,
                description=description,
                example=example
            ).__dict__
        )

    return schema

if __name__ == "__main__":
    import json

    result = build_schema(
        sample_dir="src/sample/",
        mapping_dir="src/mapping/"
    )

    with open("src/schema.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)