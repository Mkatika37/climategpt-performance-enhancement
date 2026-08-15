from flask import Flask, request, jsonify, render_template_string
import requests
import os

app = Flask(__name__)

# Configuration - ClimateGPT endpoint and credentials from your curl command
CLIMATEGPT_URL = "https://erasmus.ai/models/climategpt_8b_test/v1/chat/completions"
CLIMATEGPT_USER = "ai"
CLIMATEGPT_PASS = "4climate"
CLIMATEGPT_MODEL = "/cache/climategpt_8b_test"

# MCP Server Configuration
VIIRS_MCP_URL = os.environ.get("VIIRS_MCP_URL", "http://YOUR_SERVER_IP:8000")
AQUEDUCT_MCP_URL = os.environ.get("AQUEDUCT_MCP_URL", "http://YOUR_SERVER_IP:8001")

# Keyword patterns for routing
FIRE_KEYWORDS = [
    'fire', 'fires', 'wildfire', 'wildfires', 'burn', 'burning', 'burnt',
    'thermal', 'hotspot', 'hotspots', 'smoke', 'flame', 'viirs',
    'blaze', 'inferno', 'ignition', 'combustion'
]

WATER_KEYWORDS = [
    'water', 'flood', 'flooding', 'drought', 'precipitation', 'rainfall',
    'river', 'rivers', 'lake', 'lakes', 'stream', 'streams',
    'aquatic', 'hydro', 'hydrological', 'watershed', 'aqueduct',
    'reservoir', 'groundwater', 'aquifer'
]

# Tool definitions from MCP servers
VIIRS_TOOLS = [
    "describe_viirs_dataset", "query_recent_fires", "query_fires_by_location",
    "query_high_intensity_fires", "get_fire_statistics", "query_fires_by_date",
    "execute_custom_query", "get_coordinates", "get_bounding_box",
    "query_viirs_by_place", "count_viirs_by_place", "summarize_viirs_docs",
    "calculate_fire_ghg_emissions", "calculate_ghg_emissions_by_location",
    "calculate_ghg_emissions_by_place", "get_ghg_emissions_summary"
]

AQUEDUCT_TOOLS = [
    "list_datasets", "get_dataset_info", "query_dataset",
    "aggregate_dataset", "set_db_path", "get_document_text"
]

# Simple HTML Template for the UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ClimateGPT Chat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .chat-box {
            border: 1px solid #ddd;
            padding: 20px;
            margin: 20px 0;
            min-height: 300px;
            max-height: 500px;
            overflow-y: auto;
            background: #fafafa;
            border-radius: 5px;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
        }
        .user {
            background: #e3f2fd;
            text-align: right;
        }
        .assistant {
            background: #f1f8e9;
        }
        textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: Arial, sans-serif;
        }
        button {
            padding: 10px 20px;
            margin: 5px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        .send-btn {
            background: #4CAF50;
            color: white;
        }
        .clear-btn {
            background: #f44336;
            color: white;
        }
        .loading {
            color: #666;
            font-style: italic;
        }
        .mcp-controls {
            background: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border: 1px solid #ddd;
        }
        .mcp-controls label {
            display: inline-block;
            margin-right: 20px;
            cursor: pointer;
        }
        .mcp-controls input[type="checkbox"] {
            margin-right: 5px;
            cursor: pointer;
        }
        .mcp-status {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            margin-left: 5px;
        }
        .badge-fire {
            background: #ffebee;
            color: #c62828;
        }
        .badge-water {
            background: #e3f2fd;
            color: #1565c0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Team Pipeline ClimateGPT Chat Interface</h1>

        <div class="mcp-controls">
            <strong>MCP Data Sources:</strong><br>
            <label>
                <input type="checkbox" id="enableVIIRS" checked>
                VIIRS Fire Detection <span class="badge badge-fire">Fire Data</span>
            </label>
            <label>
                <input type="checkbox" id="enableAqueduct" checked>
                Aqueduct Water Risk <span class="badge badge-water">Water Data</span>
            </label>
            <label>
                <input type="checkbox" id="autoDetect" checked>
                Auto-detect (use keywords)
            </label>
            <div class="mcp-status" id="mcpStatus">
                Auto-detection enabled. Keywords: fire, water, etc.
            </div>
        </div>

        <div class="chat-box" id="chatBox">
            <p style="text-align: center; color: #999;">Start a conversation with ClimateGPT</p>
        </div>

        <div>
            <label for="userInput"><strong>Your Message:</strong></label>
            <textarea id="userInput" rows="3" placeholder="Ask me about climate change..."></textarea>
        </div>

        <div style="margin-top: 10px;">
            <button class="send-btn" onclick="sendMessage()">Send</button>
            <button class="clear-btn" onclick="clearChat()">Clear Chat</button>
        </div>
    </div>

    <script>
        // Update status message when checkboxes change
        function updateMCPStatus() {
            const viirs = document.getElementById('enableVIIRS').checked;
            const aqueduct = document.getElementById('enableAqueduct').checked;
            const autoDetect = document.getElementById('autoDetect').checked;
            const status = document.getElementById('mcpStatus');

            if (!viirs && !aqueduct) {
                status.textContent = 'No MCP data sources enabled. Using ClimateGPT only.';
                status.style.color = '#999';
            } else if (autoDetect) {
                const sources = [];
                if (viirs) sources.push('fire keywords → VIIRS');
                if (aqueduct) sources.push('water keywords → Aqueduct');
                status.textContent = 'Auto-detection: ' + sources.join(', ');
                status.style.color = '#4CAF50';
            } else {
                const sources = [];
                if (viirs) sources.push('VIIRS');
                if (aqueduct) sources.push('Aqueduct');
                status.textContent = 'Always query: ' + sources.join(', ');
                status.style.color = '#2196F3';
            }
        }

        // Add event listeners to checkboxes
        document.getElementById('enableVIIRS').addEventListener('change', updateMCPStatus);
        document.getElementById('enableAqueduct').addEventListener('change', updateMCPStatus);
        document.getElementById('autoDetect').addEventListener('change', updateMCPStatus);

        function addMessage(role, content, metadata) {
            const chatBox = document.getElementById('chatBox');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message ' + role;
            msgDiv.textContent = content;

            // Add metadata badge if MCP sources were used
            if (metadata && metadata.mcp_sources_used && metadata.mcp_sources_used.length > 0) {
                const badgeDiv = document.createElement('div');
                badgeDiv.style.fontSize = '0.8em';
                badgeDiv.style.marginTop = '5px';
                badgeDiv.style.color = '#666';
                badgeDiv.textContent = 'Data sources: ' + metadata.mcp_sources_used.join(', ');
                msgDiv.appendChild(badgeDiv);
            }

            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function showLoading() {
            const chatBox = document.getElementById('chatBox');
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading';
            loadingDiv.id = 'loading-indicator';
            loadingDiv.textContent = 'ClimateGPT is thinking...';
            chatBox.appendChild(loadingDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function hideLoading() {
            const loading = document.getElementById('loading-indicator');
            if (loading) loading.remove();
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const message = input.value.trim();

            if (!message) {
                alert('Please enter a message');
                return;
            }

            // Get MCP preferences
            const mcpConfig = {
                enable_viirs: document.getElementById('enableVIIRS').checked,
                enable_aqueduct: document.getElementById('enableAqueduct').checked,
                auto_detect: document.getElementById('autoDetect').checked
            };

            // Show user message
            addMessage('user', message);
            input.value = '';
            showLoading();

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: message,
                        mcp_config: mcpConfig
                    })
                });

                const data = await response.json();
                hideLoading();

                if (data.status === 'success') {
                    addMessage('assistant', data.response, data);
                } else {
                    addMessage('assistant', 'Error: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                hideLoading();
                addMessage('assistant', 'Error: Failed to connect to server');
                console.error(error);
            }
        }

        function clearChat() {
            document.getElementById('chatBox').innerHTML =
                '<p style="text-align: center; color: #999;">Start a conversation with ClimateGPT</p>';
        }

        // Allow Enter to send (Shift+Enter for new line)
        document.getElementById('userInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Initialize status
        updateMCPStatus();
    </script>
</body>
</html>
"""


def detect_keywords(text):
    """Detect which MCP server(s) should be queried based on keywords"""
    text_lower = text.lower()

    fire_detected = any(keyword in text_lower for keyword in FIRE_KEYWORDS)
    water_detected = any(keyword in text_lower for keyword in WATER_KEYWORDS)

    return {
        'fire': fire_detected,
        'water': water_detected
    }


def call_mcp_server(server_url, tool_name, arguments):
    """Call an MCP server tool and return the response"""
    try:
        payload = {
            "tool": tool_name,
            "arguments": arguments
        }

        print(f"Calling MCP: {server_url}/mcp/call_tool")
        print(f"Tool: {tool_name}, Args: {arguments}")

        response = requests.post(
            f"{server_url}/mcp/call_tool",
            json=payload,
            timeout=30
        )

        print(f"MCP Response Status: {response.status_code}")

        response.raise_for_status()
        result = response.json()

        # Check if the result has the expected format
        if "result" in result:
            print(f"MCP returned {len(str(result['result']))} chars of data")
            return result
        else:
            print(f"MCP response format: {list(result.keys())}")
            return result

    except requests.exceptions.RequestException as e:
        print(f"MCP server request failed: {e}")
        return {"error": f"MCP server call failed: {str(e)}"}
    except Exception as e:
        print(f"MCP server error: {e}")
        return {"error": f"MCP server error: {str(e)}"}


def get_mcp_data(user_message, mcp_config=None):
    """
    Analyze message and fetch relevant data from MCP servers

    Args:
        user_message: The user's message text
        mcp_config: Dict with keys:
            - enable_viirs: bool
            - enable_aqueduct: bool
            - auto_detect: bool (use keyword detection)
    """
    if mcp_config is None:
        mcp_config = {
            'enable_viirs': True,
            'enable_aqueduct': True,
            'auto_detect': True
        }

    # If both are disabled, return empty
    if not mcp_config.get('enable_viirs') and not mcp_config.get('enable_aqueduct'):
        return []

    mcp_data = []

    # Determine if we should query based on keywords or always query
    if mcp_config.get('auto_detect', True):
        keywords = detect_keywords(user_message)
        query_viirs = keywords['fire'] and mcp_config.get('enable_viirs', True)
        query_aqueduct = keywords['water'] and mcp_config.get('enable_aqueduct', True)
        print(f"Keyword detection: fire={keywords['fire']}, water={keywords['water']}")
        print(f"Will query: VIIRS={query_viirs}, Aqueduct={query_aqueduct}")
    else:
        # Always query enabled servers
        query_viirs = mcp_config.get('enable_viirs', True)
        query_aqueduct = mcp_config.get('enable_aqueduct', True)
        print(f"Auto-detect OFF: Will query VIIRS={query_viirs}, Aqueduct={query_aqueduct}")

    # Query VIIRS if enabled - try to extract location and use smart queries
    if query_viirs:
        try:
            # Try to detect location in the message
            import re
            # Look for place names (simple heuristic - could be improved)
            location_match = re.search(r'(?:in|around|near|at)\s+([A-Z][a-zA-Z\s,]+?)(?:\s+area|\s*\?|$|,)', user_message)

            if location_match:
                place_name = location_match.group(1).strip()
                print(f"Detected location: {place_name}")
                # Use place-based query
                result = call_mcp_server(VIIRS_MCP_URL, "query_viirs_by_place", {
                    "place_name": place_name,
                    "limit": 50,
                    "min_confidence": "nominal"
                })
            else:
                # Fall back to recent fires
                result = call_mcp_server(VIIRS_MCP_URL, "query_recent_fires", {
                    "hours": 168,  # Last week
                    "limit": 20,
                    "min_confidence": "nominal"
                })

            if result and "error" not in result:
                mcp_data.append({
                    "source": "VIIRS Fire Detection",
                    "data": result
                })
        except Exception as e:
            print(f"VIIRS query failed: {e}")

    # Query Aqueduct if enabled
    if query_aqueduct:
        try:
            # Get list of available datasets
            result = call_mcp_server(AQUEDUCT_MCP_URL, "list_datasets", {})
            if result and "error" not in result:
                mcp_data.append({
                    "source": "Aqueduct Water Data - Available Datasets",
                    "data": result
                })
        except Exception as e:
            print(f"Aqueduct query failed: {e}")

    return mcp_data


@app.route('/')
def index():
    """Serve the main chat UI"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat requests to ClimateGPT with MCP server integration.
    1. Get MCP configuration from request
    2. Query relevant MCP servers based on config
    3. Augment the context with MCP data
    4. Send to ClimateGPT for final response
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        mcp_config = data.get('mcp_config', {
            'enable_viirs': True,
            'enable_aqueduct': True,
            'auto_detect': True
        })

        if not user_message:
            return jsonify({
                'status': 'error',
                'error': 'Message cannot be empty'
            }), 400

        # Step 1: Check if we need to query MCP servers with user's preferences
        mcp_data = get_mcp_data(user_message, mcp_config)

        # Step 2: Build the system message - DON'T mention tools, just set role
        system_message = "You are a helpful climate science assistant. When provided with data from climate databases, analyze and summarize it to answer the user's question. Present the information clearly and concisely."

        # Step 3: If we got MCP data, add it to the context WITH CLEAR INSTRUCTIONS
        enhanced_user_message = user_message
        if mcp_data:
            enhanced_user_message += "\n\n=== DATA FROM CLIMATE DATABASES ===\n"
            for mcp_entry in mcp_data:
                enhanced_user_message += f"\n--- {mcp_entry['source']} ---\n"
                # Include more data for better context
                data_str = str(mcp_entry['data'])
                # Limit to 2000 chars to avoid token limits
                enhanced_user_message += f"{data_str[:2000]}\n"
                if len(data_str) > 2000:
                    enhanced_user_message += f"(Data truncated, {len(data_str)} total characters)\n"

            enhanced_user_message += "\n=== INSTRUCTIONS ===\n"
            enhanced_user_message += "Using the data provided above, please answer the user's question. "
            enhanced_user_message += "Summarize the findings and provide specific numbers, locations, or details from the data. "
            enhanced_user_message += "Do NOT explain how to query the data - the data has already been retrieved for you. "
            enhanced_user_message += "Just analyze and present the results.\n"

        # Step 4: Build the request payload
        payload = {
            "model": CLIMATEGPT_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": enhanced_user_message}
            ]
        }

        # Step 5: Make the request to ClimateGPT
        response = requests.post(
            CLIMATEGPT_URL,
            json=payload,
            auth=(CLIMATEGPT_USER, CLIMATEGPT_PASS),
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        response.raise_for_status()
        response_data = response.json()

        # Extract assistant's response from OpenAI-compatible format
        if 'choices' in response_data and len(response_data['choices']) > 0:
            assistant_message = response_data['choices'][0]['message']['content']
            return jsonify({
                'status': 'success',
                'response': assistant_message,
                'mcp_sources_used': [entry['source'] for entry in mcp_data] if mcp_data else []
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'Unexpected response format'
            }), 500

    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'error',
            'error': f'Failed to connect to ClimateGPT: {str(e)}'
        }), 502
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': f'Server error: {str(e)}'
        }), 500


if __name__ == '__main__':
    port = 5000
    print("\n" + "="*60)
    print("ClimateGPT Chat UI with MCP Integration")
    print("="*60)
    print(f"Web UI: http://127.0.0.1:{port}")
    print(f"ClimateGPT: {CLIMATEGPT_URL}")
    print(f"VIIRS MCP: {VIIRS_MCP_URL}")
    print(f"Aqueduct MCP: {AQUEDUCT_MCP_URL}")
    print("\nKeyword Detection:")
    print(f"  Fire keywords: {', '.join(FIRE_KEYWORDS[:5])}...")
    print(f"  Water keywords: {', '.join(WATER_KEYWORDS[:5])}...")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=port, debug=True)

