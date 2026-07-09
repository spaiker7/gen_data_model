from dataclasses import dataclass
from typing import Optional, List

import pandas as pd
from pathlib import Path

from data_utils import TabularFromFile
@dataclass
class AttrProfile:
    name: str              # target name
    source_name: str       # source column
    dtype: str
    description: str
    example: Optional[str] = None

@dataclass
class TableProfile:
    columns: List[AttrProfile]

MAPPING_REQUIRED_COLUMNS = {
    "src_name",
    "target_name",
    "description"
}


def load_mapping(mapping_dir: str) -> dict:
    """Load column mapping from CSV/XLSX.

    Returns
    -------
    dict
        {
            "<source_column>": {
                "name": "<target_column>",
                "description": "<business description>"
            }
        }
    """

    path = Path(mapping_dir)

    if not path.exists() or not any(path.iterdir()):
        return {}

    df = TabularFromFile(path).pd

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
    )

    missing = MAPPING_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Mapping file is missing required columns: {', '.join(sorted(missing))}"
        )

    mapping = {}

    for row in df.itertuples(index=False):
        mapping[str(row.src_name).strip()] = {
            "name": str(row.target_name).strip(),
            "description": "" if row.description is None else str(row.description).strip(),
        }

    return mapping