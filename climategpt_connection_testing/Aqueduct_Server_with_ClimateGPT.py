"""
DuckDB Dataset MCP Server for Claude with ClimateGPT Integration
Provides water risk data access AND AI-powered climate analysis
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import os 
import sys
import subprocess
from pypdf import PdfReader 

from mcp.server.fastmcp import FastMCP, Context
from Aqueduct_Duckdb_Handler import DuckDBDatasetHandler, DuckDBConfig

# Import ClimateGPT client
from climategpt_client import get_climate_gpt_client

# Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Global Handler and Configuration
DEFAULT_CFG = DuckDBConfig()
_handler = DuckDBDatasetHandler(DEFAULT_CFG)

# Initialize ClimateGPT client
climate_gpt = get_climate_gpt_client()

# Database loader path
AQUEDUCT_LOADER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "GMU_DAEN_2025_02_Database",
    "Source",
    "Database",
    "Aqueduct_Data_Loader.py"
)
logger.info(f"Database loader path: {AQUEDUCT_LOADER_PATH}")

# MCP app
app = FastMCP("duckdb-dataset-mcp-with-climategpt")

# -----------------------------------------------------------------------------
# EXISTING TOOLS (Keep all your original tools)
# -----------------------------------------------------------------------------

@app.tool()
def list_datasets(context: Context) -> List[str]:
    """Return all available datasets"""
    try:
        return _handler.get_available_datasets()
    except Exception as e:
        logger.exception("list_datasets failed")
        return [f"ERROR: {e}"]

@app.tool()
def get_dataset_info(context: Context, dataset_name: str) -> Dict[str, Any]:
    """Get schema info for a dataset"""
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
    """Query rows from a dataset"""
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
    """Execute aggregation query"""
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
    """Switch active DuckDB database"""
    global _handler, DEFAULT_CFG, AQUEDUCT_LOADER_PATH
    
    try:
        new_cfg = DuckDBConfig(
            db_path=db_path,
            read_only=read_only,
            csv_baseline_annual=csv_baseline_annual or DEFAULT_CFG.csv_baseline_annual,
            csv_baseline_monthly=csv_baseline_monthly or DEFAULT_CFG.csv_baseline_monthly,
            csv_future_annual=csv_future_annual or DEFAULT_CFG.csv_future_annual,
            auto_load=auto_load,
        )
        
        try:
            _handler.close()
        except Exception:
            pass

        _handler = DuckDBDatasetHandler(new_cfg)
        DEFAULT_CFG = new_cfg

        db_needs_load = False
        
        if not os.path.exists(db_path):
            logger.warning(f"DuckDB file not found at {db_path}. Load required.")
            db_needs_load = True
        
        if not db_needs_load:
            try:
                datasets = _handler.get_available_datasets()
                if not datasets:
                    logger.warning("DB exists but empty. Load required.")
                    db_needs_load = True
            except Exception as e:
                logger.error(f"Error checking DB: {e}")
                db_needs_load = True

        if db_needs_load:
            logger.info(f"Running loader: {AQUEDUCT_LOADER_PATH}")
            subprocess.run([sys.executable, AQUEDUCT_LOADER_PATH], check=True)
            logger.info("Loader finished successfully.")
            _handler = DuckDBDatasetHandler(DEFAULT_CFG)
            _ = _handler.get_available_datasets()

        return {"status": "ok", "db_path": db_path, "auto_load": auto_load}
    except subprocess.CalledProcessError as e:
        logger.exception(f"Loader failed: {e}")
        return {"error": f"Load failed: {e.returncode}"}
    except Exception as e:
        logger.exception("set_db_path failed")
        return {"error": str(e)}

@app.tool()
def get_document_text(context: Context, document_name: str) -> Dict[str, Any]:
    """Read PDF from Docs directory"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    DOCS_DIR = os.path.join(project_root, "Docs")
    file_path = os.path.join(DOCS_DIR, document_name)
    
    if not os.path.exists(file_path):
        return {"error": f"Document not found: {file_path}"}
    
    if not file_path.lower().endswith('.pdf'):
        return {"error": f"Not a PDF: {document_name}"}

    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        
        char_count = len(text)
        max_snippet_length = 2000
        
        if char_count > max_snippet_length:
            snippet = text[:max_snippet_length] + f"\n\n... (Total: {char_count} chars)"
        else:
            snippet = text

        return {
            "document_name": document_name,
            "char_count": char_count,
            "full_text_available": char_count <= max_snippet_length,
            "content": snippet
        }
    except Exception as e:
        logger.exception(f"get_document_text failed for {document_name}")
        return {"error": f"Failed to read PDF: {str(e)}"}

# -----------------------------------------------------------------------------
# NEW CLIMATEGPT INTEGRATION TOOLS
# -----------------------------------------------------------------------------

@app.tool()
def ask_climategpt_about_water_risk(
    context: Context,
    question: str,
    water_data_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ask ClimateGPT to analyze water risk data or answer climate-related 
    questions about water stress, drought, and water availability.
    
    Args:
        question: Your question about water risks, climate impacts, or drought
        water_data_context: Optional water data to provide as context
    
    Returns:
        ClimateGPT's analysis and response
    """
    try:
        if water_data_context:
            response = climate_gpt.analyze_water_risk(water_data_context, question)
        else:
            response = climate_gpt.query(
                question,
                system_prompt=(
                    "You are ClimateGPT, specialized in water resources, "
                    "climate change impacts on water systems, and drought analysis."
                )
            )
        
        if response:
            return {
                "status": "success",
                "question": question,
                "analysis": response
            }
        else:
            return {"error": "Could not get response from ClimateGPT"}
    
    except Exception as e:
        logger.exception("ask_climategpt_about_water_risk failed")
        return {"error": str(e)}

@app.tool()
def get_water_risk_climate_analysis(
    context: Context,
    location_or_region: str,
    dataset_name: str = "aqueduct.baseline_annual"
) -> Dict[str, Any]:
    """
    Get ClimateGPT's analysis of water risk data for a specific location/region
    with climate context and adaptation recommendations.
    
    Args:
        location_or_region: Location name or region (e.g., 'California', 'Nile Basin')
        dataset_name: Aqueduct dataset to query (default: baseline_annual)
    
    Returns:
        Water risk data + ClimateGPT's climate analysis
    """
    try:
        # Query water risk data (you may need to adjust this based on your schema)
        water_data = _handler.query_dataset(
            dataset_name,
            filters={"string_id": location_or_region},  # Adjust filter as needed
            limit=10
        )
        
        if not water_data or "error" in water_data:
            return {"error": f"No water data found for '{location_or_region}'"}
        
        # Create summary for ClimateGPT
        summary = f"Water Risk Data for {location_or_region}:\n"
        if "data" in water_data:
            summary += f"Records found: {len(water_data['data'])}\n"
            summary += str(water_data)
        
        # Get ClimateGPT analysis
        analysis = climate_gpt.analyze_water_risk(summary)
        
        if analysis:
            return {
                "status": "success",
                "location": location_or_region,
                "water_data": water_data,
                "climate_analysis": analysis
            }
        else:
            return {
                "status": "partial",
                "water_data": water_data,
                "error": "Could not get ClimateGPT analysis"
            }
    
    except Exception as e:
        logger.exception("get_water_risk_climate_analysis failed")
        return {"error": str(e)}

@app.tool()
def compare_water_risk_scenarios(
    context: Context,
    baseline_query: Dict[str, Any],
    future_query: Dict[str, Any],
    location: str
) -> Dict[str, Any]:
    """
    Compare baseline and future water risk scenarios and get ClimateGPT's 
    analysis of climate change impacts.
    
    Args:
        baseline_query: Query parameters for baseline data
        future_query: Query parameters for future projection data
        location: Location being analyzed
    
    Returns:
        Comparison data + ClimateGPT's climate impact analysis
    """
    try:
        # Query baseline data
        baseline_data = _handler.query_dataset(
            "aqueduct.baseline_annual",
            filters=baseline_query.get("filters"),
            columns=baseline_query.get("columns"),
            limit=10
        )
        
        # Query future data
        future_data = _handler.query_dataset(
            "aqueduct.future_annual",
            filters=future_query.get("filters"),
            columns=future_query.get("columns"),
            limit=10
        )
        
        # Create comparison summary
        summary = (
            f"Water Risk Scenario Comparison for {location}\n\n"
            f"Baseline Data:\n{baseline_data}\n\n"
            f"Future Projection Data:\n{future_data}"
        )
        
        # Get ClimateGPT analysis
        analysis = climate_gpt.analyze_water_risk(
            summary,
            "Compare these water risk scenarios and explain the climate change impacts."
        )
        
        if analysis:
            return {
                "status": "success",
                "location": location,
                "baseline_data": baseline_data,
                "future_data": future_data,
                "climate_analysis": analysis
            }
        else:
            return {
                "status": "partial",
                "baseline_data": baseline_data,
                "future_data": future_data,
                "error": "Could not get ClimateGPT analysis"
            }
    
    except Exception as e:
        logger.exception("compare_water_risk_scenarios failed")
        return {"error": str(e)}

@app.tool()
def explain_water_stress_indicators(
    context: Context,
    indicator_data: str
) -> Dict[str, Any]:
    """
    Get ClimateGPT to explain water stress indicators and their climate implications.
    
    Args:
        indicator_data: Water stress indicator values (e.g., from query results)
    
    Returns:
        ClimateGPT's explanation of the indicators
    """
    try:
        explanation = climate_gpt.query(
            f"Explain these water stress indicators and their climate implications:\n\n{indicator_data}",
            system_prompt=(
                "You are ClimateGPT, an expert in water resource indicators and climate impacts. "
                "Explain technical water stress metrics in clear, accessible language."
            )
        )
        
        if explanation:
            return {
                "status": "success",
                "explanation": explanation
            }
        else:
            return {"error": "Could not get explanation from ClimateGPT"}
    
    except Exception as e:
        logger.exception("explain_water_stress_indicators failed")
        return {"error": str(e)}

# -----------------------------------------------------------------------------
# Run Server
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Aqueduct Dataset + ClimateGPT MCP Server...")
    app.run()
