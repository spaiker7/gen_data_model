### Automatic DBT Model & Confluence Documentation Generator

Generate an entire Data Warehouse skeleton from a single sample data file using Jinja templates for dbt models and confluence pages.

This project automatically creates:
- data profiling & schema inference from your data sample (`schema.json`)
- dbt models (Stage → Raw Vault → Data Marts → Export)
- dbt model specifications (`schema.yml`)
- confluence documentation (HTML + automatic publishing)

The goal is to reduce repetitive work when onboarding a new source system while keeping documentation and implementation synchronized.

## Pipeline

### 1. Schema sample

Input:

- sample CSV/XLSX (`your_sample.{csv, xlsx}`)
- mapping file (`your_mapping.{csv, xlsx}`) <br>
  Should contain source attribute name (src_name) from sample, target attribute name (name) and its description.
Output: `src/schema.json`

The schema contains
- target name
- source name
- logical datatype (defined in data_utils.infer_dtype func)
- description
- example value

Additional metadata technical columns and generated hash keys should be provided in `dbt_config.yaml`. They are automatically appended to the models and published pages during generation.

### 2. DBT models

Input:
- `src/schema.json`
- `configs/dbt_config.yaml`
  
Output: (`dbt/models/`) <br>
For every generated model a corresponding specification is created automatically based on `dbt/templates/specs/model_spec.yml`.

### 3. Documentation

Input: <br>
- generated models `dbt/models/*.sql`
- generated `src/schema.json`
- `configs/dbt_config.yaml`
- `configs/docs_config.yaml`
  - page titles
  - Confluence parent pages
  - table names
  - schemas
  - update schedules
  - templates
  - technical columns
- `configs/db_types_aliases.yaml` (maps logical datatypes to database-specific datatypes)

Output:
- HTML documentation (`confl/pages/`)
- published Confluence pages <br>
  Pages are generated as HTML and optionally published using the Atlassian Python API. <br>
  Required environment variables:
  ```
  CONFLUENCE_BASE_URL=
  CONFLUENCE_TOKEN=
  CONFLUENCE_SPACE=
  CONFLUENCE_VERIFY_SSL=false
  ```

### Project Structure

```
├── configs/
│   ├── db_types_aliases.yaml
│   ├── dbt_config.yaml
│   └── docs_config.yaml
├── confl/
│   ├── generate_pages.py
│   └── jnj_templates/
│       ├── clickhouse/
│       │   └── mart_ch_page_jnj_template.html
│       ├── greenplum/
│       │   ├── mart_gp_page_jnj_template.html
│       │   ├── raw_vault_gp_page_jnj_template.html
│       │   └── stg_gp_page_jnj_template.html
│       └── hadoop/
│           ├── stg_hdp_page_jnj_template.html
│           └── stg_hdp_page_jnj_template_sample.html
├── dbt/
│   ├── models/
│   ├── spec/
│   ├── templates/
│   │   ├── models/
│   │   │   ├── export/
│   │   │   │   └── export_part2ch_template.sql
│   │   │   ├── marts/
│   │   │   │   └── mart_from_file_template.sql
│   │   │   ├── raw_stage/
│   │   │   │   └── raw_stage_template.sql
│   │   │   ├── raw_vault/
│   │   │   │   ├── hsats/
│   │   │   │   │   └── hsat_template.sql
│   │   │   │   ├── hubs/
│   │   │   │   │   └── hub_template.sql
│   │   │   │   ├── links/
│   │   │   │   └── lsats/
│   │   │   └── stage/
│   │   │       └── stage_template.sql
│   │   └── specs/
│   │       └── model_spec.yml
│   └── generate_models.py
└── src/
│   ├── profiler.py
│   ├── sample/
│   │   └── your_sample.csv
│   ├── mapping/
│   │   └── your_mapping.csv
│   └── schema_models.py
├── data_utils.py
├── README.md
```

---
