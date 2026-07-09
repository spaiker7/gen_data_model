import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from atlassian import Confluence

from data_utils import TemplateGenerator

logger = logging.getLogger(__name__)

class DocumentationGenerator(TemplateGenerator):
    """
    Generate Confluence documentation pages from metadata and Jinja templates.
    """

    def __init__(
        self,
        doc_config_path: str | Path,
        dbt_config_path: str | Path,
        schema_path: str | Path,
        output_dir: str | Path = "confl/pages",
        dtype_aliases: str | Path = "db_types_aliases.yaml",
        template_root: str | Path = "."
    ):
        super().__init__(template_root)

        self.doc_cfg = self._load_yaml(doc_config_path)
        self.dbt_cfg = self._load_yaml(dbt_config_path)
        self.schema = self._load_json(schema_path)
        self.dtype_aliases = self._load_yaml(dtype_aliases)

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.paths = self.doc_cfg["paths"]
        self.docs = self.doc_cfg["confluence"]

        self.load_env()
        self.connect()

        self.load_models()
        self.load_specs()

        self.add_tech_attrs_to_schema()
        self.schema_lookup = {col["name"]: col for col in self.schema}

    def add_tech_attrs_to_schema(self):
        """
        Append technical attributes from dbt_config to the schema.
        """

        for group in self.dbt_cfg.get("technical_attrs", {}).values():
            for col in group:
                self.schema.append({
                    "name": col["name"],
                    "source_name": col.get("source_name", ""),
                    "dtype": col.get("dtype", ""),
                    "description": col.get("description", ""),
                    "example": col.get("example", ""),
                })

    def load_env(self):

        dotenv_path = Path(__file__).parent / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path)

        self.env_cfg = {
            "confluence_token": os.getenv("CONFLUENCE_TOKEN", ""),
            "confluence_base_url": os.getenv("CONFLUENCE_BASE_URL", ""),
            "confluence_space": os.getenv("CONFLUENCE_SPACE", ""),
            "verify_ssl": os.getenv("CONFLUENCE_VERIFY_SSL", "false").lower() == "true"
        }

    def get_dtype(self, logical_type: str, database: str):
        return self.dtype_aliases.get(logical_type.lower(), {}).get(database, logical_type)

    def connect(self):
        self.confluence = Confluence(
            url=self.env_cfg["confluence_base_url"],
            token=self.env_cfg["confluence_token"],
            verify_ssl=self.env_cfg["verify_ssl"]
        )

    def publish_page(self, title, html_path, parent_id):

        body = html_path.read_text(encoding="utf-8")

        self.confluence.create_page(
            space=self.env_cfg["confluence_space"],
            title=title,
            body=body,
            parent_id=parent_id,
            representation="storage"
        )
        logger.info("Published page '%s'", title)
        
    def load_models(self):
        self.models = {}
        model_dir = Path(self.paths["models"])
        for file in model_dir.glob("*.sql"):
            self.models[file.stem] = file.read_text(
                encoding="utf-8"
            )

    def load_specs(self):
        self.specs = {}
        spec_dir = Path(self.paths["specs"])
        for file in spec_dir.glob("*.yml"):

            self.specs[file.stem] = self._load_yaml(file)

    def build_context(self, **kwargs):
        return {
            "schema": self.schema,
            "models": self.models,
            "specs": self.specs,
            **kwargs
        }

    def build_attrs(self, *, db_dtypes, model_name, formula_builder=None):
        """
        Build attrs expected by Confluence template.
        """
        attrs = []
        spec = self.specs[model_name]

        for col in spec["models"][0]["columns"]:
            schema_col = self.schema_lookup[col["name"]]
            if schema_col is None:
                logger.warning("Column '%s' not found in schema.json", col["name"])
                continue
            attrs.append((
                schema_col["name"],
                schema_col.get("description", ""),
                self.get_dtype(schema_col["dtype"], db_dtypes),
                formula_builder(schema_col) if formula_builder else "",
                "",
                schema_col.get("example", ""),
            ))

        return attrs

    def render_publish_page(
        self,
        *,
        title: str,
        parent_id: str,
        template_path: str,
        context: dict
    ):
        output_path = self.output_dir / f"{title}.html"

        self.render_to_file(
            output_path=output_path,
            template_path=template_path,
            context=context
        )

        self.publish_page(
            title=title,
            html_path=output_path,
            parent_id=parent_id
        )

    def generate_source_page(self):
        page_cfg = self.docs["source"]

        attrs = self.build_attrs(
            model_name=self.models_cfg["raw_stage"]["model_name"],
            db_dtypes=page_cfg["db_dtypes"],
            formula_builder=lambda c: 
                f"<*{page_cfg['extension']}>/{c['source_name']}"
        )

        self.render_publish_page(
            title=page_cfg["title"],
            parent_id=page_cfg["parent_page_id"],
            template_path=page_cfg["template_path"],
            context=self.build_context(
                attrs=attrs,
                **page_cfg
            )
        )

    def generate_stage_page(self):
        page_cfg = self.docs["stage"]

        attrs = self.build_attrs(
            model_name=self.models_cfg["stage"]["model_name"],
            db_dtypes=page_cfg["db_dtypes"],
            formula_builder=lambda c:
                 f"{self.docs['source']['schema_name']}.{self.docs['source']['table_name']}.{c['name']}".upper()
        )
        self.render_publish_page(
            title=page_cfg["title"],
            parent_id=page_cfg["parent_page_id"],
            template_path=page_cfg["template_path"],
            context=self.build_context(
                attrs=attrs,
                raw_stage_model=self.models.get(self.models_cfg["raw_stage"]["model_name"], ""),
                stage_model=self.models.get(self.models_cfg["stage"]["model_name"],  ""),
                raw_stage_model_spec=self.specs.get(self.models_cfg["raw_stage"]["model_name"],{}),
                stage_model_spec=self.specs.get(self.models_cfg["stage"]["model_name"], {}),
                **page_cfg
            )
        )

    def generate_hubs(self):
        for hub in self.models_cfg["raw_vault"]["hubs"]:
            page_cfg = next((cfg for cfg in self.docs["hubs"]if cfg["model_name"] == hub["model_name"]), None)
            attrs = self.build_attrs(
                model_name=hub["model_name"],
                db_dtypes=page_cfg["db_dtypes"],
                formula_builder=lambda c:
                    f"{self.docs["stage"]["schema_name"]}.{self.docs["stage"]['table_name']}.{c['name']}".upper()                
            )
            self.render_publish_page(
                title=page_cfg["title"],
                parent_id=page_cfg["parent_page_id"],
                template_path=page_cfg["template_path"],
                context=self.build_context(
                    attrs=attrs,
                    model=self.models.get(hub["model_name"], {}),
                    model_spec=self.specs.get(hub["model_name"], {}),
                    **page_cfg
                )
            )

    def generate_hsats(self):
        for hsat in self.models_cfg["raw_vault"]["hsats"]:
            page_cfg = next((cfg for cfg in self.docs["hsats"]if cfg["model_name"] == hsat["model_name"]), None)
            attrs = self.build_attrs(
                model_name=hsat["model_name"],
                db_dtypes=page_cfg["db_dtypes"],
                formula_builder=lambda c:
                    f"{self.docs["stage"]["schema_name"]}.{self.docs["stage"]['table_name']}.{c['name']}".upper()                 
            )
            self.render_publish_page(
                title=page_cfg["title"],
                parent_id=page_cfg["parent_page_id"],
                template_path=page_cfg["template_path"],
                context=self.build_context(
                    attrs=attrs,
                    model=self.models.get(hsat["model_name"], {}),
                    model_spec=self.specs.get(hsat["model_name"], {}),
                    **page_cfg
                )
            )

    def generate_marts(self):
        for mart in self.models_cfg["marts"]:
            # greenplum
            page_cfg = next((cfg for cfg in self.docs["base_marts"]if cfg["model_name"] == mart["model_name"]), None)
            export = next((e for e in self.models_cfg["export"] if e["source_model"] == mart["model_name"]), None)
            attrs = self.build_attrs(
                model_name=mart["model_name"],
                db_dtypes=page_cfg["db_dtypes"]
            )
            self.render_publish_page(
                title=page_cfg["title"],
                parent_id=page_cfg["parent_page_id"],
                template_path=page_cfg["template_path"],
                context=self.build_context(
                    attrs=attrs,
                    datamart_model=self.models.get(mart["model_name"], ""),
                    export_part2ch_model=self.models.get(export["model_name"], "") if export else "",
                    datamart_model_spec=self.specs.get(mart["model_name"], {}),
                    export_part2ch_model_spec=self.specs.get(export["model_name"], {}) if export else {},
                    **page_cfg
                )
         
            )
            # clickhouse   
            page_cfg = next((cfg for cfg in self.docs["marts"]if cfg["model_name"] == mart["model_name"]), None)
            attrs = self.build_attrs(
                model_name=mart["model_name"],
                db_dtypes=page_cfg["db_dtypes"]
            )
            self.render_publish_page(
                title=page_cfg["title"],
                parent_id=page_cfg["parent_page_id"],
                template_path=page_cfg["template_path"],
                context=self.build_context(
                    attrs=attrs,
                    **page_cfg
                )
            )

    def generate(self):

        logger.info("Generating Confluence pages...")

        self.generate_source_page()
        self.generate_stage_page()

        self.generate_hubs()
        self.generate_hsats()

        self.generate_marts()

        logger.info("Documentation generation completed.")

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    generator = DocumentationGenerator(
        doc_config_path="configs/doc_config.yaml",
        dbt_config_path="configs/dbt_config.yaml",
        schema_path="src/schema.json"
    )

    generator.generate()