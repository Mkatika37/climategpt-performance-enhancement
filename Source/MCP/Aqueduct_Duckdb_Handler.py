"""
DuckDB-backed dataset handler for MCP server (container-safe, zero-config).
- Auto-discovers DB in /data or Source/Database
- Env overrides supported (AQUEDUCT_DUCKDB_PATH, *_CSV_*)
- Filename-only resolution (Windows paths OK)
- Auto-load CSVs only when writable
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# pandas optional; fall back to Arrow
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------- Config dataclass -------------------------------

@dataclass
class DuckDBConfig:
    # Leave paths None by default; we resolve them at runtime.
    db_path: Optional[str] = None
    read_only: bool = True
    csv_baseline_annual: Optional[str] = None
    csv_baseline_monthly: Optional[str] = None
    csv_future_annual: Optional[str] = None
    csv_region_lookup: Optional[str] = None
    auto_load: bool = True  # honored only when read_only=False


# ---------------------------- Handler ---------------------------------------

class DuckDBDatasetHandler:
    """
    Handles listing, introspection, querying, and summarizing datasets stored as tables in a DuckDB database.
    Auto-discovers a .duckdb in container mounts and optionally auto-loads CSVs into tables when missing.
    """

    def __init__(self, config: Optional[DuckDBConfig] = None):
        self._conn = None  # type: ignore

        # --- Paths we will search in the container ---
        self._script_dir = os.path.dirname(os.path.abspath(__file__))               # .../Source/MCP
        self._project_root = os.path.dirname(os.path.dirname(self._script_dir))     # .../
        self._DATA_DIRS = [
            "/data",
            os.path.join(self._project_root, "Source", "Database"),
        ]

        # Build config: env → provided config → autodetect
        env_ro = os.getenv("AQUEDUCT_DUCKDB_READONLY") or os.getenv("AQUEDUCT_DB_READONLY")
        read_only = _str2bool(env_ro, config.read_only if config else True)

        # Resolve DB path: env > config > autodetect
        env_db = os.getenv("AQUEDUCT_DUCKDB_PATH")
        conf_db = (config.db_path if config else None) if config else None
        db_path = self._resolve_db_path(env_db or conf_db)

        # Resolve CSVs (env or by filename in known dirs)
        csv_baseline_annual = self._resolve_data_path(
            os.getenv("AQUEDUCT_CSV_BASELINE_ANNUAL") or (config.csv_baseline_annual if config else None)
        )
        csv_baseline_monthly = self._resolve_data_path(
            os.getenv("AQUEDUCT_CSV_BASELINE_MONTHLY") or (config.csv_baseline_monthly if config else None)
        )
        csv_future_annual = self._resolve_data_path(
            os.getenv("AQUEDUCT_CSV_FUTURE_ANNUAL") or (config.csv_future_annual if config else None)
        )
        csv_region_lookup = self._resolve_data_path(
            os.getenv("AQUEDUCT_CSV_REGION_LOOKUP") or (getattr(config, "csv_region_lookup", None) if config else None)
        )

        auto_load = _str2bool(os.getenv("AQUEDUCT_AUTO_LOAD"), config.auto_load if config else True)

        self.config = DuckDBConfig(
            db_path=db_path,
            read_only=read_only,
            csv_baseline_annual=csv_baseline_annual,
            csv_baseline_monthly=csv_baseline_monthly,
            csv_future_annual=csv_future_annual,
            csv_region_lookup=csv_region_lookup,
            auto_load=auto_load,
        )

        # Helpful debug
        logger.info(
            "Effective config: db=%s read_only=%s auto_load=%s",
            self.config.db_path, self.config.read_only, self.config.auto_load
        )
        logger.debug("Data dirs: %s", self._DATA_DIRS)

    # -- Connection management -------------------------------------------------

    def _duckdb(self):
        return importlib.import_module("duckdb")

    def _connect(self):
        if self._conn is not None:
            return self._conn

        if not self.config.db_path:
            # Try one last autodiscovery
            self.config.db_path = self._autodetect_duckdb()
        if not self.config.db_path:
            raise RuntimeError("No DuckDB file found. Mount a .duckdb to /data or set AQUEDUCT_DUCKDB_PATH.")

        db_dir = os.path.dirname(self.config.db_path)
        if db_dir and not os.path.exists(db_dir) and not self.config.read_only:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                logger.warning("Could not create DB directory '%s': %s", db_dir, e)

        if self.config.read_only and not os.path.exists(self.config.db_path):
            raise RuntimeError(f"DuckDB file not found (read-only mode): {self.config.db_path}")

        duckdb = self._duckdb()
        self._conn = duckdb.connect(database=self.config.db_path, read_only=self.config.read_only)

        # Only attempt autoload when writable
        if self.config.auto_load and not self.config.read_only:
            try:
                self._ensure_aqueduct_tables()
            except Exception as e:
                logger.warning("Auto-load failed: %s", e)

        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # -- Auto-load Aqueduct tables --------------------------------------------

    def _ensure_aqueduct_tables(self) -> None:
        """
        Ensure the three Aqueduct tables (+ Region_Lookup) exist.
        If missing and CSV path exists, create from CSV. Requires read_only=False.
        """
        con = self._conn or self._connect()

        required = {
            "Baseline_Annual": self.config.csv_baseline_annual,
            "Baseline_Monthly": self.config.csv_baseline_monthly,
            "Future_Annual": self.config.csv_future_annual,
            "Region_Lookup": self.config.csv_region_lookup,
        }

        missing: List[str] = []
        for table in required:
            if not self._table_exists(con, "main", table):
                missing.append(table)

        if not missing:
            return

        if self.config.read_only:
            raise RuntimeError(
                "DB opened read-only, but required tables are missing: "
                f"{missing}. Reopen with read_only=False or create tables beforehand."
            )

        for table, csv_path in required.items():
            if not self._table_exists(con, "main", table):
                if not csv_path or not os.path.exists(csv_path):
                    logger.info("Table %s missing; CSV not found at %s; skipping.", table, csv_path)
                    continue
                logger.info("Creating table %s from %s", table, csv_path)
                path_sql = self._escape_sql_string(csv_path)
                con.execute(
                    f'CREATE TABLE {self._quote_ident(table)} AS '
                    f"SELECT * FROM read_csv_auto('{path_sql}');"
                )

    # -- Dataset (table) discovery --------------------------------------------

    def get_available_datasets(self, schema_filter: Optional[List[str]] = None) -> List[str]:
        con = self._connect()
        if schema_filter:
            placeholders = ",".join(["?"] * len(schema_filter))
            q = f"""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema IN ({placeholders})
                ORDER BY table_schema, table_name
            """
            rows = con.execute(q, schema_filter).fetchall()
        else:
            q = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name
            """
            rows = con.execute(q).fetchall()

        return [f"{s}.{t}" for s, t in rows]

    # -- Dataset info ----------------------------------------------------------

    def get_dataset_info(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        schema, table = self._parse_name(dataset_name)
        con = self._connect()

        exists = con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema, table],
        ).fetchone()[0]
        if exists == 0:
            return None

        row_count = con.execute(
            f'SELECT COUNT(*) FROM {self._qname(schema, table)}'
        ).fetchone()[0]

        cols_rel = con.execute(f'PRAGMA table_info({self._qname(schema, table)})')
        if pd is not None:
            cols_df = cols_rel.fetchdf()
            dtypes = {r["name"]: r["type"] for _, r in cols_df.iterrows()}
            columns = list(cols_df["name"].values)
        else:
            at = cols_rel.fetch_arrow_table()
            names = at.column("name").to_pylist()
            types = at.column("type").to_pylist()
            dtypes = dict(zip(names, types))
            columns = list(names)

        return {
            "name": f"{schema}.{table}",
            "rows": int(row_count),
            "columns": columns,
            "dtypes": dtypes,
            "description": f"DuckDB table {schema}.{table} with {row_count} rows and {len(columns)} columns",
        }

    # -- Query (with Region_Lookup join for main tables) ----------------------

    def query_dataset(
        self,
        dataset_name: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        schema, table = self._parse_name(dataset_name)
        con = self._connect()
        if not self._table_exists(con, schema, table):
            return None  # Changed "Non" to "None"

        is_main_table = table in ["Baseline_Annual", "Baseline_Monthly", "Future_Annual"]

        if is_main_table:
            # LEFT JOIN Region_Lookup on pfaf_id
            if columns:
                # Filter out 'region_name' if it's explicitly requested in `columns`.
                base_cols = [c for c in columns if c != "region_name"]
                
                # Prefix all columns from the main table (t).
                select_cols_prefixed = [f"t.{self._quote_ident(c)}" for c in base_cols]
                
                # Always select the region_name from the joined table (rl) with an alias.
                select_cols = ", ".join(select_cols_prefixed)
                if select_cols:
                    select_cols += ", "
                select_cols += "rl.region_name AS region_name"
            else:
                # If no columns are specified, select everything from the main table (t.*) and region_name from the lookup.
                select_cols = "t.*, rl.region_name AS region_name"
            
            sql = (
                f"SELECT {select_cols} FROM {self._qname(schema, table)} AS t "
                f'LEFT JOIN "main"."Region_Lookup" AS rl ON t.pfaf_id = rl.pfaf_id'
            )
        else:
            # For non-main tables, use the original logic
            select_cols = "*" if not columns else ", ".join(self._quote_ident(c) for c in columns)
            sql = f"SELECT {select_cols} FROM {self._qname(schema, table)}"

        params: List[Any] = []
        where_clauses: List[str] = []
        if filters:
            for col, val in filters.items():
                col_q = self._quote_ident(col)
                if is_main_table and col != "region_name":
                    col_q = f"t.{col_q}"
                elif is_main_table and col == "region_name":
                    col_q = f"rl.{col_q}"

                if isinstance(val, dict):
                    if "min" in val and "max" in val:
                        where_clauses.append(f"{col_q} BETWEEN ? AND ?")
                        params.extend([val["min"], val["max"]])
                    elif "min" in val:
                        where_clauses.append(f"{col_q} >= ?")
                        params.append(val["min"])
                    elif "max" in val:
                        where_clauses.append(f"{col_q} <= ?")
                        params.append(val["max"])
                elif isinstance(val, list):
                    if len(val) == 0:
                        where_clauses.append("1=0")
                    else:
                        placeholders = ", ".join(["?"] * len(val))
                        where_clauses.append(f"{col_q} IN ({placeholders})")
                        params.extend(val)
                else:
                    where_clauses.append(f"{col_q} = ?")
                    params.append(val)

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        if limit and isinstance(limit, int) and limit > 0:
            sql += f" LIMIT {int(limit)}"

        rel = con.execute(sql, params)
        if pd is not None:
            df = rel.fetchdf()
            data = df.to_dict(orient="records")
            columns_out = list(df.columns)
        else:
            at = rel.fetch_arrow_table()
            data = at.to_pylist()
            columns_out = at.column_names

        return {"data": data, "count": len(data), "columns": list(columns_out)}

    # -- Aggregate (with Region_Lookup join support) --------------------------

    def aggregate_dataset(
        self,
        dataset_name: str,
        aggregate_expressions: List[str],
        group_by: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        having: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        schema, table = self._parse_name(dataset_name)
        con = self._connect()
        if not self._table_exists(con, schema, table):
            return None

        is_main_table = table in ["Baseline_Annual", "Baseline_Monthly", "Future_Annual"]

        params: List[Any] = []
        if is_main_table:
            from_clause = (
                f"{self._qname(schema, table)} AS t "
                f'LEFT JOIN "main"."Region_Lookup" AS rl ON t.pfaf_id = rl.pfaf_id'
            )
            if group_by:
                sel_parts = []
                for c in group_by:
                    sel_parts.append('rl."region_name" AS region_name' if c == "region_name" else f't.{self._quote_ident(c)}')
                select_cols = ", ".join(sel_parts) + (", " if sel_parts else "")
            else:
                select_cols = ""
            select_cols += ", ".join(aggregate_expressions)
            sql = f"SELECT {select_cols} FROM {from_clause}"
            group_cols_q = (
                ", ".join(['rl."region_name"' if c == "region_name" else f't.{self._quote_ident(c)}' for c in group_by])
                if group_by else ""
            )
        else:
            from_clause = self._qname(schema, table)
            prefix = ", ".join(group_by) + ", " if group_by else ""
            select_cols = prefix + ", ".join(aggregate_expressions)
            sql = f"SELECT {select_cols} FROM {from_clause}"
            group_cols_q = ", ".join(self._quote_ident(c) for c in group_by) if group_by else ""

        where_clauses: List[str] = []
        if filters:
            for col, val in filters.items():
                col_q = self._quote_ident(col)
                if is_main_table and col != "region_name":
                    col_q = f"t.{col_q}"
                elif is_main_table and col == "region_name":
                    col_q = f"rl.{col_q}"

                if isinstance(val, dict):
                    if "min" in val and "max" in val:
                        where_clauses.append(f"{col_q} BETWEEN ? AND ?")
                        params.extend([val["min"], val["max"]])
                    elif "min" in val:
                        where_clauses.append(f"{col_q} >= ?")
                        params.append(val["min"])
                    elif "max" in val:
                        where_clauses.append(f"{col_q} <= ?")
                        params.append(val["max"])
                elif isinstance(val, list):
                    if len(val) == 0:
                        where_clauses.append("1=0")
                    else:
                        placeholders = ", ".join(["?"] * len(val))
                        where_clauses.append(f"{col_q} IN ({placeholders})")
                        params.extend(val)
                else:
                    where_clauses.append(f"{col_q} = ?")
                    params.append(val)

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        if group_cols_q:
            sql += f" GROUP BY {group_cols_q}"
        if having:
            sql += f" HAVING {having}"

        logger.info("Aggregate SQL: %s  params=%s", sql, params)
        rel = con.execute(sql, params)
        if pd is not None:
            df = rel.fetchdf()
            data = df.to_dict(orient="records")
            columns_out = list(df.columns)
        else:
            at = rel.fetch_arrow_table()
            data = at.to_pylist()
            columns_out = at.column_names
        return {"data": data, "count": len(data), "columns": list(columns_out)}

    # -- Summary (unchanged style) --------------------------------------------

    def get_dataset_summary(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        schema, table = self._parse_name(dataset_name)
        con = self._connect()
        if not self._table_exists(con, schema, table):
            return None
        rel = con.execute(f"SELECT * FROM {self._qname(schema, table)}")

        summary: Dict[str, Any] = {}
        if pd is not None:
            df = rel.fetchdf()
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                summary["numeric"] = df[numeric_cols].describe().to_dict()
            categorical_cols = df.select_dtypes(include=["object", "category"]).columns
            if len(categorical_cols) > 0:
                summary["categorical"] = {}
                for col in categorical_cols:
                    vc = df[col].value_counts().head(10)
                    summary["categorical"][col] = {
                        "unique_count": int(df[col].nunique()),
                        "top_values": {str(k): int(v) for k, v in vc.items()},
                    }
        else:
            at = rel.fetch_arrow_table()
            summary["columns"] = at.column_names
            summary["row_count"] = at.num_rows
        return summary

    # -- Helpers ---------------------------------------------------------------

    def _resolve_db_path(self, candidate: Optional[str]) -> Optional[str]:
        """Accept absolute path, Windows path, or filename; search known dirs."""
        if candidate and os.path.exists(candidate):
            return candidate
        if candidate:
            hit = self._resolve_data_path(candidate, ext=".duckdb")
            if hit:
                return hit
        return self._autodetect_duckdb()

    def _autodetect_duckdb(self) -> Optional[str]:
        cands = self._list_files(ext=".duckdb")
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        for c in cands:
            if "aqueduct" in os.path.basename(c).lower():
                return c
        return max(cands, key=lambda p: os.path.getmtime(p))

    def _resolve_data_path(self, p: Optional[str], ext: Optional[str] = None) -> Optional[str]:
        """Resolve p which may be absolute, Windows path, or filename; search known dirs."""
        if not p:
            return None
        p_norm = _normalize_path(p)
        if os.path.exists(p_norm):
            return p_norm
        base = os.path.basename(p_norm)
        if ext and not base.lower().endswith(ext):
            return None
        for d in self._DATA_DIRS:
            cand = os.path.join(d, base)
            if os.path.exists(cand):
                return cand
        return None

    def _list_files(self, ext: str) -> List[str]:
        out: List[str] = []
        for d in self._DATA_DIRS:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith(ext):
                        out.append(os.path.join(d, f))
        return out

    @staticmethod
    def _parse_name(name: str) -> Tuple[str, str]:
        return ("main", name) if "." not in name else tuple(name.split(".", 1))  # type: ignore

    @staticmethod
    def _quote_ident(ident: str) -> str:
        return f'"{ident}"'

    @staticmethod
    def _qname(schema: str, table: str) -> str:
        return f'"{schema}"."{table}"'

    @staticmethod
    def _escape_sql_string(s: str) -> str:
        return s.replace("'", "''")

    @staticmethod
    def _table_exists(con, schema: str, table: str) -> bool:
        q = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
        """
        return con.execute(q, [schema, table]).fetchone()[0] > 0


# ---------------------------- small utils ------------------------------------

def _str2bool(s: Optional[str], default: bool = False) -> bool:
    return default if s is None else s.strip().lower() in {"1", "true", "yes", "y", "on"}

def _normalize_path(p: str) -> str:
    """Normalize Windows or mixed separators to POSIX-ish; return usable path/filename."""
    return p.replace("\\", "/")


