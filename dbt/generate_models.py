from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader

from data_utils import TemplateGenerator

logger = logging.getLogger(__name__)

class DBTGenerator(TemplateGenerator):
    """
    Generates dbt SQL models from Jinja templates and YAML configuration.
    """

    def __init__(
        self,
        config_path: str | Path,
        schema_path: str | Path,
        models_dir: str | Path = "dbt/models",
        spec_dir: str | Path = "dbt/spec",        
        template_root: str | Path = "."
    ):
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path)
        self.models_dir = Path(models_dir)
        self.spec_dir = Path(spec_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.spec_dir.mkdir(parents=True, exist_ok=True)

        self.cfg = self._load_yaml(self.config_path)
        self.schema = self._load_json(self.schema_path)

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

    
    def generate_raw_stage(self) -> None:
        cfg = self.cfg["models"]["raw_stage"]

        context = {
            "table_name": self.cfg["source"]["table"],
        }
        model_name=cfg["model_name"]
        self.render_to_file(
            output_path=self.models_dir / f"{model_name}.sql",
            template_path=cfg["template"],
            context=context,
        )

    def generate_stage(self) -> None:
        cfg = self.cfg["models"]["stage"]

        context = {
            "source_model": self.cfg["models"]["raw_stage"]["model_name"],
            "hash_keys": cfg["hash_keys"],
        }

        model_name=cfg["model_name"]
        self.render_to_file(
            output_path=self.models_dir / f"{model_name}.sql",
            template_path=cfg["template"],
            context=context,
        )

    def generate_hubs(self) -> None:
        rv_cfg = self.cfg["models"].get("raw_vault", {})

        for hub_cfg in rv_cfg.get("hubs", []):

            context = {
                **hub_cfg,
                "source_model": self.cfg["models"]["stage"]["model_name"],
            }

            model_name=hub_cfg["model_name"]
            self.render_to_file(
                output_path=self.models_dir / f"{model_name}.sql",
                template_path=hub_cfg["template"],
                context=context,
            )

    def generate_hsats(self) -> None:
        rv_cfg = self.cfg["models"].get("raw_vault", {})
        for hsat_cfg in rv_cfg.get("hsats", []):

            context = {
                **hsat_cfg,
                "source_model": self.cfg["models"]["stage"]["model_name"],
            }

            model_name=hsat_cfg["model_name"]
            self.render_to_file(
                output_path=self.models_dir / f"{model_name}.sql",
                template_path=hsat_cfg["template"],
                context=context,
            )

    def generate_marts(self) -> None:
        for mart_cfg in self.cfg["models"].get("marts", []):
            model_name=mart_cfg["model_name"]
            self.render_to_file(
                output_path=self.models_dir / f"{model_name}.sql",
                template_path=mart_cfg["template"],
                context=mart_cfg,
            )

    def generate_exports(self) -> None:
        for export_cfg in self.cfg["models"].get("export", []):
            model_name=export_cfg["model_name"]
            self.render_to_file(
                output_path=self.models_dir / f"{model_name}.sql",
                template_path=export_cfg["template"],
                context=export_cfg,
            )

    def _schema_descriptions(self) -> dict[str, str]:

        return {
            col["name"]: col.get("description", "")
            for col in self.schema
        }
        
    def _render_spec(
        self,
        *,
        model_name: str,
        model_description: str,
        columns: list[str],
        template_path: str = "dbt/templates/specs/model_spec.yml",
    ):
        schema = self._schema_descriptions()

        context = {
            "model_name": model_name,
            "model_description": model_description,
            "columns": [
                {
                    "name": c,
                    "description": schema.get(c, "")
                }
                for c in columns
            ]
        }

        spec = self.render_template(template_path, context)
        outfile = self.spec_dir / f"{model_name}.yml"
        self.save(outfile, spec)

    def generate_specs(self):

        schema_columns = [c["name"] for c in self.schema]

        technical_columns = [
            "source",
            "doc_id",
            "batch_id",
            "load_date"
        ]

        raw_cfg = self.cfg["models"]["raw_stage"]
        self._render_spec(
            model_name=raw_cfg["model_name"],
            model_description=raw_cfg.get("description", ""),
            columns=self.unique(
                schema_columns,
                technical_columns
            )
        )

        stage_cfg = self.cfg["models"]["stage"]
        hash_columns = list(stage_cfg["hash_keys"].keys())
        self._render_spec(
            model_name=stage_cfg["model_name"],
            model_description=stage_cfg.get("description", ""),
            columns=self.unique(
                hash_columns,
                schema_columns,
                technical_columns
            )
        )

        for hub in self.cfg["models"]["raw_vault"]["hubs"]:
            cols = self.unique(
                [hub["src_pk"]],
                hub["src_nk"],
                [
                    hub["src_ldts"],
                    hub["src_source"]
                ]
            )
            self._render_spec(
                model_name=hub["model_name"],
                model_description=hub.get("description", ""),
                columns=cols
            )

        for hsat in self.cfg["models"]["raw_vault"]["hsats"]:
            cols = self.unique(
                [hsat["src_pk"]],
                [hsat["src_hashdiff"]],
                hsat["src_payload"],
                [
                    hsat["src_eff"],
                    hsat["src_ldts"],
                    hsat["src_source"]
                ]
            )
            self._render_spec(
                model_name=hsat["model_name"],
                model_description=hsat.get("description", ""),
                columns=cols
            )

        for mart in self.cfg["models"].get("marts", []):
            cols = self.unique(
                [mart["src_pk"]],
                mart["src_nk"],
                mart["src_payload"],
                [
                    mart["src_eff"],
                    'load_date',
                    'source'
                ]
            )
            self._render_spec(
                model_name=mart["model_name"],
                model_description=mart.get("description", ""),
                columns=cols
            )

        for export in self.cfg["models"].get("export", []):
            mart = next((m for m in self.cfg["models"]["marts"]
                    if m["model_name"] == export["source_model"]
                ), None)
            if mart is None:
                continue
            cols = self.unique(
                [mart["src_pk"]],
                mart["src_nk"],
                mart["src_payload"],
                [
                    mart["src_eff"]
                ]
            )
            self._render_spec(
                model_name=export["model_name"],
                model_description=export.get("description", ""),
                columns=cols
            )

    def generate(self) -> None:

        logger.info("Generating dbt models...")
        self.generate_raw_stage()
        self.generate_stage()
        self.generate_hubs()
        self.generate_hsats()
        self.generate_marts()
        self.generate_exports()

        logger.info("Generating dbt specs...")
        self.generate_specs()
        logger.info("Done.")

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    generator = DBTGenerator(
        config_path="configs/dbt_config.yaml",
        schema_path="src/schema.json",
        models_dir="dbt/models",
    )

    generator.generate()