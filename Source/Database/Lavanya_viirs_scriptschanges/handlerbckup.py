"""
DuckDB-backed dataset handler for VIIRS thermal hotspot data.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import importlib

# pandas is optional
try:
    import pandas as pd
except Exception:
    pd = None

logger = logging.getLogger(__name__)


@dataclass
class VIIRSConfig:
    # Default DB path - update to your actual path
    db_path: str = r"C:\Users\ASUS\GMU_DAEN_2025_02_D\Source\Database\VIIRS_Thermal_Database.duckdb"
    # Read-only by default since data is populated by ETL script
    read_only: bool = True


class VIIRSDuckDBHandler:
    """
    Handles listing, introspection, querying, and summarizing VIIRS thermal hotspot data
    stored in a DuckDB database.
    """

    def __init__(self, config: Optional[VIIRSConfig] = None):
        self.config = config or VIIRSConfig(
            db_path=os.environ.get("VIIRS_DUCKDB_PATH", VIIRSConfig.db_path),
            read_only=(os.environ.get("VIIRS_DUCKDB_READONLY", "true").lower() == "true"),
        )
        self._conn = None

    # -- Connection management -------------------------------------------------
    def _duckdb(self):
        return importlib.import_module("duckdb")

    def _connect(self):
        if self._conn is None:
            duckdb = self._duckdb()
            
            if not os.path.exists(self.config.db_path):
                raise FileNotFoundError(
                    f"VIIRS database not found at {self.config.db_path}. "
                    "Please run the ETL script first to create the database."
                )
            
            self._conn = duckdb.connect(
                database=self.config.db_path, read_only=self.config.read_only
            )

        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

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
            name_idx = at.column_names.index("name")
            type_idx = at.column_names.index("type")
            names = at.columns[name_idx].to_pylist()
            types = at.columns[type_idx].to_pylist()
            dtypes = dict(zip(names, types))
            columns = list(names)

        return {
            "name": f"{schema}.{table}",
            "rows": int(row_count),
            "columns": columns,
            "dtypes": dtypes,
            "description": f"VIIRS thermal hotspot data: {row_count} fire detections across {len(columns)} attributes",
        }

    # -- Query -----------------------------------------------------------------
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
            return None

        select_cols = "*" if not columns else ", ".join([self._quote_ident(c) for c in columns])
        sql = f"SELECT {select_cols} FROM {self._qname(schema, table)}"
        params: List[Any] = []

        where_clauses: List[str] = []
        if filters:
            for col, val in filters.items():
                col_q = self._quote_ident(col)
                if isinstance(val, dict):
                    # Range filter: { "min": ..., "max": ... }
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
            columns_out = at.column_names
            records = at.to_pylist()
            data = records

        return {
            "data": data,
            "count": len(data),
            "columns": list(columns_out),
        }

    # -- Summary ---------------------------------------------------------------
    def get_dataset_summary(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        schema, table = self._parse_name(dataset_name)
        con = self._connect()
        if not self._table_exists(con, schema, table):
            return None

        rel = con.execute(f"SELECT * FROM {self._qname(schema, table)}")

        summary: Dict[str, Any] = {}

        if pd is not None:
            df = rel.fetchdf()

            # Numeric stats (brightness temps, FRP, etc.)
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                summary["numeric"] = df[numeric_cols].describe().to_dict()

            # Categorical stats (satellite, confidence, day/night)
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
    @staticmethod
    def _parse_name(name: str) -> Tuple[str, str]:
        if "." in name:
            schema, table = name.split(".", 1)
        else:
            schema, table = "main", name
        return schema, table

    @staticmethod
    def _quote_ident(ident: str) -> str:
        return f'"{ident}"'

    @staticmethod
    def _qname(schema: str, table: str) -> str:
        return f'"{schema}"."{table}"'

    @staticmethod
    def _table_exists(con, schema: str, table: str) -> bool:
        q = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
        """
        return con.execute(q, [schema, table]).fetchone()[0] > 0
