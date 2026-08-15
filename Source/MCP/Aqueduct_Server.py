"""
DuckDB Dataset MCP Server (FastMCP over stdio)
Exposes data and document access tools to an MCP-compatible LLM host.
 
Tools
-----
- list_datasets()
- get_dataset_info(dataset_name)
- query_dataset(dataset_name, filters?, columns?, limit?)
- aggregate_dataset(dataset_name, aggregate_expressions, group_by?, filters?, having?)
- set_db_path(db_path, read_only?, csv_baseline_annual?, csv_baseline_monthly?, csv_future_annual?, auto_load?)
- get_document_text(document_name)
"""
 
from __future__ import annotations
 
import asyncio
import inspect
import logging
import os
import subprocess
import sys
import time
import traceback
from typing import Any, Dict, List, Optional
 
from pypdf import PdfReader
from mcp.server.fastmcp import FastMCP, Context
 
from Aqueduct_Duckdb_Handler import DuckDBDatasetHandler, DuckDBConfig
 
# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("duckdb-dataset-mcp")
 
# -----------------------------------------------------------------------------
# Global Handler and Configuration
# -----------------------------------------------------------------------------
DEFAULT_CFG = DuckDBConfig()
_handler = DuckDBDatasetHandler(DEFAULT_CFG)
 
# Compute project root relative to this file:
#   <project_root>/Source/MCP/this_file.py  -> project_root = dirname(dirname(script_dir))
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_script_dir))
 
# Optional database loader script:
AQUEDUCT_LOADER_PATH = os.path.join(_project_root, "Source", "Database", "Aqueduct_Data_Loader.py")
logger.info(f"Database loader path: {AQUEDUCT_LOADER_PATH}")
 
# PDF reading constants
PDF_SNIPPET_MAX = 2000
 
# MCP app
app = FastMCP("duckdb-dataset-mcp")
 
 
# -----------------------------------------------------------------------------
# Tool Definitions
# -----------------------------------------------------------------------------
@app.tool()
def list_datasets(context: Context) -> List[str]:
    """Return all available datasets (schema.table) found in DuckDB."""
    try:
        return _handler.get_available_datasets()
    except Exception as e:
        logger.exception("list_datasets failed")
        # Keep return type as List[str] to match the tool signature
        return [f"ERROR: {e}"]
 
 
@app.tool()
def get_dataset_info(context: Context, dataset_name: str) -> Dict[str, Any]:
    """Get schema info (row count, columns, dtypes) for a dataset."""
    try:
        info = _handler.get_dataset_info(dataset_name)
        return info or {"error": f"Dataset not found: {dataset_name}"}
    except Exception as e:
        logger.exception("get_dataset_info failed")
        return {"error": str(e)}
 
 
@app.tool()
def query_dataset(
    context: Context,
    dataset_name: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    limit: Optional[int] = 10,
) -> Dict[str, Any]:
    """Query rows from a dataset with optional filters and selected columns."""
    try:
        result = _handler.query_dataset(dataset_name, filters=filters, columns=columns, limit=limit)
        return result or {"error": f"Dataset not found: {dataset_name}"}
    except Exception as e:
        logger.exception("query_dataset failed")
        return {"error": str(e)}
 
 
@app.tool()
def aggregate_dataset(
    context: Context,
    dataset_name: str,
    aggregate_expressions: List[str],
    group_by: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    having: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run aggregation queries (AVG/SUM/COUNT/MIN/MAX, etc.) with optional GROUP BY,
    WHERE (via filters), and HAVING clause.
    """
    try:
        result = _handler.aggregate_dataset(
            dataset_name=dataset_name,
            aggregate_expressions=aggregate_expressions,
            group_by=group_by,
            filters=filters,
            having=having,
        )
        return result or {"error": f"Dataset not found: {dataset_name}"}
    except Exception as e:
        logger.exception("aggregate_dataset failed")
        return {"error": str(e)}
 
 
@app.tool()
def set_db_path(
    context: Context,
    db_path: str,
    read_only: bool = False,
    csv_baseline_annual: Optional[str] = None,
    csv_baseline_monthly: Optional[str] = None,
    csv_future_annual: Optional[str] = None,
    auto_load: bool = True,
) -> Dict[str, Any]:
    """
    Switch the active DuckDB database and (optionally) CSV autoload paths.
    Closes the old connection, reinitializes, and if the DB is missing/empty,
    optionally runs Aqueduct_Data_Loader.py to populate it.
    """
    global _handler, DEFAULT_CFG
 
    try:
        # 1) Build new config
        new_cfg = DuckDBConfig(
            db_path=db_path,
            read_only=read_only,
            csv_baseline_annual=csv_baseline_annual or DEFAULT_CFG.csv_baseline_annual,
            csv_baseline_monthly=csv_baseline_monthly or DEFAULT_CFG.csv_baseline_monthly,
            csv_future_annual=csv_future_annual or DEFAULT_CFG.csv_future_annual,
            auto_load=auto_load,
        )
 
        # 2) Close old connection (best-effort)
        try:
            _handler.close()
        except Exception:
            logger.debug("Previous handler close() raised but ignored.", exc_info=True)
 
        # 3) Swap handler/config
        _handler = DuckDBDatasetHandler(new_cfg)
        DEFAULT_CFG = new_cfg
 
        # 4) Determine if DB needs loading
        db_needs_load = not os.path.exists(db_path)
        if not db_needs_load:
            try:
                datasets = _handler.get_available_datasets()
                if not datasets:
                    logger.warning("DuckDB file exists but contains no datasets. Load required.")
                    db_needs_load = True
            except Exception as e:
                logger.error(f"Error checking new DB; assuming load is needed: {e}")
                db_needs_load = True
 
        # 5) Run loader if needed (and if script exists)
        if db_needs_load:
            if os.path.exists(AQUEDUCT_LOADER_PATH):
                logger.info(f"Running database loader script: {AQUEDUCT_LOADER_PATH}")
                # Inherit current environment; add any helpful hints
                env = os.environ.copy()
                if DEFAULT_CFG.csv_baseline_annual:
                    env.setdefault("AQUEDUCT_CSV_BASELINE_ANNUAL", DEFAULT_CFG.csv_baseline_annual)
                if DEFAULT_CFG.csv_baseline_monthly:
                    env.setdefault("AQUEDUCT_CSV_BASELINE_MONTHLY", DEFAULT_CFG.csv_baseline_monthly)
                if DEFAULT_CFG.csv_future_annual:
                    env.setdefault("AQUEDUCT_CSV_FUTURE_ANNUAL", DEFAULT_CFG.csv_future_annual)
 
                subprocess.run([sys.executable, AQUEDUCT_LOADER_PATH], check=True, env=env)
                logger.info("Database loader finished successfully.")
                # Re-init after load
                _handler = DuckDBDatasetHandler(DEFAULT_CFG)
                # Pre-warm
                _ = _handler.get_available_datasets()
            else:
                msg = f"DB needs load but loader script not found at: {AQUEDUCT_LOADER_PATH}"
                logger.error(msg)
                return {"error": msg}
        else:
            # 6) Pre-warm
            _ = _handler.get_available_datasets()
 
        return {"status": "ok", "db_path": db_path, "auto_load": auto_load}
    except subprocess.CalledProcessError as e:
        logger.exception("Database loader failed during set_db_path")
        return {"error": f"Database load failed with exit code {e.returncode}. See server logs."}
    except Exception as e:
        logger.exception("set_db_path failed")
        return {"error": str(e)}
 
 
@app.tool()
def get_document_text(context: Context, document_name: str) -> Dict[str, Any]:
    """
    Reads a specified PDF file from the 'Docs' directory (sibling of /Source),
    extracts text, and returns a snippet.
    """
    project_root = _project_root
    docs_dir = os.path.join(project_root, "Docs")
    file_path = os.path.join(docs_dir, document_name)
 
    print(f"DEBUG: Checking full path: {file_path}", file=sys.stderr)
 
    if not os.path.exists(file_path):
        return {"error": f"Document not found. Checked path: {file_path}"}
 
    if not file_path.lower().endswith(".pdf"):
        return {"error": f"File is not a PDF: {document_name}. Only PDF files are supported."}
 
    try:
        reader = PdfReader(file_path)
        text_parts: List[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
 
        text = "\n\n".join(text_parts)
        char_count = len(text)
        if char_count == 0:
            return {
                "document_name": document_name,
                "char_count": 0,
                "full_text_available": True,
                "content": "",
                "warning": "No extractable text found in this PDF (might be scanned images).",
            }
 
        if char_count > PDF_SNIPPET_MAX:
            snippet = text[:PDF_SNIPPET_MAX] + f"\n\n... (Text truncated. Total characters: {char_count})"
            full_text_available = False
        else:
            snippet = text
            full_text_available = True
 
        return {
            "document_name": document_name,
            "char_count": char_count,
            "full_text_available": full_text_available,
            "content": snippet,
        }
    except Exception as e:
        logger.exception(f"get_document_text failed for {document_name}")
        return {"error": f"Failed to read or parse PDF: {str(e)}"}
 
 
# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
def _print_startup_debug() -> None:
    """Print diagnostic info and safely resolve async/sync list_tools()."""
    try:
        print("DEBUG: Starting FastMCP (stdio) server", file=sys.stderr)
        print(f"DEBUG: python={sys.version.split()[0]} os={sys.platform} cwd={os.getcwd()}", file=sys.stderr)
        print(f"DEBUG: sys.path (first 10): {sys.path[:10]}", file=sys.stderr)
 
        try:
            import mcp  # type: ignore
            print(
                f"DEBUG: mcp module: {getattr(mcp, '__file__', None)} "
                f"version={getattr(mcp, '__version__', None)}",
                file=sys.stderr,
            )
        except Exception:
            print("DEBUG: unable to import mcp metadata", file=sys.stderr)
 
        # Show registered tools (supports both sync and async list_tools)
        tools_repr = None
        if hasattr(app, "list_tools"):
            try:
                val = app.list_tools()
                if inspect.isawaitable(val):
                    try:
                        tools_repr = asyncio.run(val)
                    except RuntimeError:
                        # If an event loop is already running, don't crash—just note it.
                        tools_repr = "<async list_tools (event loop active; not awaited here)>"
                else:
                    tools_repr = val
            except Exception as e:
                tools_repr = f"<list_tools error: {e}>"
 
        print(f"DEBUG: registered tools: {tools_repr}", file=sys.stderr)
    except Exception:
        traceback.print_exc(file=sys.stderr)
 
 
def _run_stdio_server() -> None:
    """
    Prefer async stdio runner if available; otherwise fall back to sync run().
    """
    _print_startup_debug()
    try:
        run_stdio_async = getattr(app, "run_stdio_async", None)
        if callable(run_stdio_async):
            asyncio.run(run_stdio_async())  # type: ignore[misc]
        else:
            # Fallback: some FastMCP versions accept (transport="stdio")
            try:
                app.run("stdio")  # type: ignore[arg-type]
            except TypeError:
                # Old API might be app.run() -> default to stdio
                app.run()  # type: ignore[call-arg]
    except KeyboardInterrupt:
        print("DEBUG: KeyboardInterrupt received; shutting down.", file=sys.stderr)
    except Exception:
        print("ERROR: exception raised from FastMCP run:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        sys.stderr.flush()
        if os.getenv("MCP_DEBUG_HOLD"):
            print("DEBUG: MCP_DEBUG_HOLD set - entering sleep (Ctrl+C to exit)", file=sys.stderr)
            sys.stderr.flush()
            while True:
                time.sleep(3600)
 
 
if __name__ == "__main__":
    logger.info("Starting DuckDB Dataset & PDF MCP Server (FastMCP over stdio)...")
    _run_stdio_server()
 


