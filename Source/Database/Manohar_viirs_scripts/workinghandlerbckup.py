"""
DuckDB-backed dataset handler for VIIRS thermal hotspot data.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    db_path: str = r".\Source\Database\VIIRS_Thermal_Database.duckdb"
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

    # -- Serialization helper --------------------------------------------------
    @staticmethod
    def _serialize_for_json(obj: Any) -> Any:
        """
        Convert non-JSON-serializable objects to JSON-serializable format.
        Handles datetime, pandas Timestamp, and nested structures.
        """
        if pd and isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: VIIRSDuckDBHandler._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [VIIRSDuckDBHandler._serialize_for_json(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Handle other complex objects
            return str(obj)
        return obj

    # -- Count fires by days back ----------------------------------------------
    def count_fires_by_days(
        self,
        dataset_name: str,
        days_back: float,
        group_by: Optional[List[str]] = None,
        additional_filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Count fires detected within the last N days based on acquisition_timestamp.
        
        Args:
            dataset_name: Name of the table
            days_back: Number of days to look back from now (can be fractional, e.g., 0.5 for 12 hours)
            group_by: Optional grouping columns
            additional_filters: Additional filters to apply (e.g., confidence, satellite)
            
        Returns:
            Dictionary with count results
        """
        # Calculate the cutoff datetime
        cutoff_datetime = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')
        
        # Build filters
        filters = additional_filters.copy() if additional_filters else {}
        filters['acquisition_timestamp'] = {'min': cutoff_str}
        
        # Call the main count_fires method
        result = self.count_fires(dataset_name, filters=filters, group_by=group_by)
        
        if result:
            # Add time range context
            result['time_range'] = {
                'days_back': days_back,
                'cutoff_datetime': cutoff_str,
                'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        return result

    # -- Count fires -----------------------------------------------------------
    def count_fires(
        self,
        dataset_name: str,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Count fire detections with optional filters and grouping.
        Efficient for "how many fires" queries without returning all records.
        
        Args:
            dataset_name: Name of the table to query
            filters: Dictionary of column filters (same format as query_dataset)
            group_by: Optional list of columns to group by
            
        Returns:
            Dictionary with count results and optional grouping breakdown
        """
        schema, table = self._parse_name(dataset_name)
        con = self._connect()
        if not self._table_exists(con, schema, table):
            return None

        # Build SELECT clause
        if group_by:
            group_cols = ", ".join([self._quote_ident(c) for c in group_by])
            select_clause = f"{group_cols}, COUNT(*) as fire_count"
        else:
            select_clause = "COUNT(*) as fire_count"

        sql = f"SELECT {select_clause} FROM {self._qname(schema, table)}"
        params: List[Any] = []

        # Build WHERE clause
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

        # Add GROUP BY if specified
        if group_by:
            group_cols = ", ".join([self._quote_ident(c) for c in group_by])
            sql += f" GROUP BY {group_cols}"
            sql += " ORDER BY fire_count DESC"

        rel = con.execute(sql, params)
        
        if group_by:
            # Return grouped results
            if pd is not None:
                df = rel.fetchdf()
                results = df.to_dict(orient="records")
            else:
                at = rel.fetch_arrow_table()
                results = at.to_pylist()
            
            # Serialize for JSON
            results = [self._serialize_for_json(record) for record in results]
            total_count = sum(r.get('fire_count', 0) for r in results)
            
            return {
                "total_count": total_count,
                "grouped_results": results,
                "group_by": group_by,
                "filters_applied": filters if filters else {},
            }
        else:
            # Return simple count
            count = rel.fetchone()[0]
            return {
                "fire_count": int(count),
                "filters_applied": filters if filters else {},
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
            
            # Convert datetime columns to strings for JSON serialization
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].astype(str)
            
            data = df.to_dict(orient="records")
            columns_out = list(df.columns)
        else:
            at = rel.fetch_arrow_table()
            columns_out = at.column_names
            records = at.to_pylist()
            
            # Convert datetime objects to strings in each record
            data = []
            for record in records:
                converted_record = {}
                for key, value in record.items():
                    # Handle datetime objects
                    if isinstance(value, datetime):
                        converted_record[key] = value.isoformat()
                    # Handle pandas Timestamp if pandas is available
                    elif pd and isinstance(value, pd.Timestamp):
                        converted_record[key] = value.isoformat()
                    else:
                        converted_record[key] = value
                data.append(converted_record)

        # Additional safety: serialize the entire data structure
        data = [self._serialize_for_json(record) for record in data]

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


