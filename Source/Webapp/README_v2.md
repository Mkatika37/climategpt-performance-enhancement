# ClimateGPT Pipeline App v2

A Flask-based web UI that integrates ClimateGPT with MCP (Model Context Protocol) servers for fire and water data.

## Features

### 1. **ClimateGPT Integration**
- Direct connection to ClimateGPT using OpenAI-compatible API
- Chat-based interface for natural language queries

### 2. **Intelligent MCP Routing**
- **Keyword Detection**: Automatically detects fire-related or water-related queries
- **VIIRS MCP**: Triggered by keywords like `fire`, `wildfire`, `burn`, `thermal`, `hotspot`
- **Aqueduct MCP**: Triggered by keywords like `water`, `flood`, `drought`, `river`, `precipitation`

### 3. **Data Augmentation**
- Queries relevant MCP servers based on detected keywords
- Injects real-time data into the context sent to ClimateGPT
- ClimateGPT uses this data to provide informed, data-driven responses

## Architecture

```
User Query
    ↓
Keyword Detection
    ↓
    ├─→ Fire keywords? → Query VIIRS MCP
    └─→ Water keywords? → Query Aqueduct MCP
    ↓
Augment Context with MCP Data
    ↓
Send to ClimateGPT
    ↓
Return Enhanced Response
```

## Configuration

### Environment Variables

```bash
# ClimateGPT (required)
CLIMATEGPT_URL=https://erasmus.ai/models/climategpt_8b_test/v1/chat/completions
CLIMATEGPT_USER=ai
CLIMATEGPT_PASS=4climate

# MCP Servers (optional, defaults to localhost)
VIIRS_MCP_URL=http://127.0.0.1:8000
AQUEDUCT_MCP_URL=http://127.0.0.1:8001
```

### MCP Server Endpoints

The app expects MCP servers to expose:
- `POST /mcp/call_tool` - Tool execution endpoint

Payload format:
```json
{
  "tool": "tool_name",
  "arguments": {}
}
```

## Running the Application

### Prerequisites

1. **Install dependencies**:
   ```bash
   pip install flask requests
   ```

2. **Start MCP Servers** (if using):
   ```bash
   # Terminal 1 - VIIRS MCP
   cd Source/MCP
   python viirs_mcp_server.py

   # Terminal 2 - Aqueduct MCP
   cd Source/MCP
   python Aqueduct_Server.py
   ```

3. **Start the Flask app**:
   ```bash
   cd Source/Webapp
   python pipeline_app_v2.py
   ```

4. **Open browser**: http://127.0.0.1:5000

## Example Queries

### Fire-related queries (triggers VIIRS MCP):
- "Show me recent wildfires in California"
- "What are the current fire hotspots?"
- "Calculate greenhouse gas emissions from recent fires"

### Water-related queries (triggers Aqueduct MCP):
- "What are the drought conditions in Texas?"
- "Show me flood risk data for the Midwest"
- "What datasets are available for water analysis?"

### General queries (ClimateGPT only):
- "What is climate change?"
- "Explain the greenhouse effect"
- "What causes rising sea levels?"

## Available Tools

### VIIRS Fire Detection Tools
- `describe_viirs_dataset` - Dataset metadata
- `query_recent_fires` - Recent fire detections
- `query_fires_by_location` - Geographic fire queries
- `query_viirs_by_place` - Place-based fire queries
- `calculate_ghg_emissions_by_place` - GHG emissions estimation
- And 11 more...

### Aqueduct Water Risk Tools
- `list_datasets` - Available water datasets
- `get_dataset_info` - Dataset schema information
- `query_dataset` - Query water risk data
- `aggregate_dataset` - Aggregate queries
- `get_document_text` - PDF document reading
- And 1 more...

## How It Works

1. **User submits a question** via the web UI
2. **Keyword detection** analyzes the question for fire/water terms
3. **MCP servers are queried** if relevant keywords are detected
4. **Context augmentation**: MCP data is added to the user's message
5. **ClimateGPT processes** the augmented request with context
6. **Response is returned** to the user with data sources indicated

## Differences from v1

- **Simpler architecture**: No complex tool routing or decision models
- **Keyword-based routing**: Instead of LLM-based tool selection
- **Stateless**: Each request is independent
- **Lighter weight**: Fewer dependencies, easier to debug
- **More reliable**: No dependency on climategpt_client wrapper

## Troubleshooting

### MCP servers not responding
- Check that MCP servers are running on expected ports
- Verify firewall/network settings
- Check server logs for errors

### No data augmentation occurring
- Verify keywords are present in your query
- Check MCP_URL configuration
- Look for error messages in Flask console

### ClimateGPT connection issues
- Verify credentials (CLIMATEGPT_USER, CLIMATEGPT_PASS)
- Check network connectivity to erasmus.ai
- Ensure URL is correct

## Development

To add new keywords:
```python
# In pipeline_app_v2.py
FIRE_KEYWORDS = [
    'fire', 'fires', 'wildfire', 'wildfires',
    # Add your keywords here
]
```

To add new MCP servers:
1. Add configuration URL
2. Define keywords for routing
3. Add tool list
4. Update `get_mcp_data()` function

## License

Part of GMU DAEN 2025 02 D Project

