"""
ClimateGPT Pipeline App v3 - True MCP Tool Calling Architecture

This version implements proper MCP tool calling where:
1. Tool definitions are fetched dynamically from MCP servers
2. Tools are sent to ClimateGPT in OpenAI function calling format
3. ClimateGPT decides which tools to call and with what parameters
4. Tools are executed and results sent back to ClimateGPT
5. Process repeats up to MAX_ITERATIONS times until final answer
"""

from flask import Flask, request, jsonify, render_template_string, send_from_directory
import requests
import json
import os

app = Flask(__name__)

# Configuration - ClimateGPT endpoint and credentials
CLIMATEGPT_URL = "https://erasmus.ai/models/climategpt_8b_test/v1/chat/completions"
CLIMATEGPT_USER = "ai"
CLIMATEGPT_PASS = "4climate"
CLIMATEGPT_MODEL = "/cache/climategpt_8b_test"

# MCP Server Configuration - Default to OpenStack server
VIIRS_MCP_URL = os.environ.get("VIIRS_MCP_URL", "http://YOUR_SERVER_IP:8000")
AQUEDUCT_MCP_URL = os.environ.get("AQUEDUCT_MCP_URL", "http://YOUR_SERVER_IP:8001")

# Maximum tool calling iterations
MAX_ITERATIONS = 10

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Team Pipeline ClimateGPT Chat</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 50px auto;
            padding: 20px;
            background-image: url('/static/PipelineApp_Background.png');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
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
            margin-bottom: 5px;
        }
        .version {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
            font-style: italic;
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
        .tool-calls {
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 10px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 12px;
        }
        .tool-call {
            margin: 5px 0;
            padding: 5px;
            background: #fff;
            border-radius: 3px;
        }
        .tool-name {
            color: #ff6f00;
            font-weight: bold;
        }
        textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: Arial, sans-serif;
            resize: vertical;
        }
        button {
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #45a049;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .controls {
            margin: 15px 0;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        .checkbox-group {
            margin: 10px 0;
        }
        label {
            margin-right: 20px;
            cursor: pointer;
        }
        .status {
            font-size: 12px;
            color: #666;
            margin-top: 10px;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 5px;
        }
        .badge-viirs {
            background: #ff5722;
            color: white;
        }
        .badge-aqueduct {
            background: #2196F3;
            color: white;
        }
        .iteration-info {
            color: #666;
            font-size: 12px;
            font-style: italic;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Team Pipeline ClimateGPT Chat</h1>
        <div class="version">Version 3.0 - MCP Tool Calling Architecture</div>

        <div class="controls">
            <div class="checkbox-group">
                <label>
                    <input type="checkbox" id="enableVIIRS" checked>
                    Enable VIIRS (Fire Data) <span class="badge badge-viirs">MCP</span>
                </label>
                <label>
                    <input type="checkbox" id="enableAqueduct" checked>
                    Enable Aqueduct (Water Data) <span class="badge badge-aqueduct">MCP</span>
                </label>
            </div>
            <div class="status">
                MCP Servers: VIIRS (YOUR_SERVER_IP:8000) | Aqueduct (YOUR_SERVER_IP:8001)
            </div>
        </div>

        <div class="chat-box" id="chatBox">
            <p style="text-align: center; color: #999;">
                Ask a question and ClimateGPT will use MCP tools to find data
            </p>
        </div>

        <textarea id="userInput" rows="3" placeholder="Ask about climate, fires, or water resources..."></textarea>
        <br><br>
        <button onclick="sendMessage()" id="sendBtn">Send</button>

        <div class="status" id="statusText"></div>
    </div>

    <script>
        const chatBox = document.getElementById('chatBox');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        const statusText = document.getElementById('statusText');

        function addMessage(text, className, toolCalls = null, iterations = null) {
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message ' + className;
            msgDiv.textContent = text;

            if (toolCalls && toolCalls.length > 0) {
                const toolDiv = document.createElement('div');
                toolDiv.className = 'tool-calls';
                toolDiv.innerHTML = '<strong>🔧 Tools Used:</strong><br>';

                toolCalls.forEach(tool => {
                    const toolCallDiv = document.createElement('div');
                    toolCallDiv.className = 'tool-call';
                    const argsStr = tool.args ? JSON.stringify(tool.args).substring(0, 100) : '';
                    toolCallDiv.innerHTML = `<span class="tool-name">${tool.name}</span> ${argsStr}`;
                    toolDiv.appendChild(toolCallDiv);
                });

                if (iterations) {
                    const iterDiv = document.createElement('div');
                    iterDiv.className = 'iteration-info';
                    iterDiv.textContent = `Completed in ${iterations} iteration(s)`;
                    toolDiv.appendChild(iterDiv);
                }

                msgDiv.appendChild(toolDiv);
            }

            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function sendMessage() {
            const message = userInput.value.trim();
            if (!message) return;

            // Get MCP configuration
            const enableVIIRS = document.getElementById('enableVIIRS').checked;
            const enableAqueduct = document.getElementById('enableAqueduct').checked;

            // Add user message to chat
            addMessage(message, 'user');
            userInput.value = '';

            // Disable send button
            sendBtn.disabled = true;
            statusText.textContent = 'ClimateGPT is thinking and calling tools...';

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        mcp_config: {
                            enable_viirs: enableVIIRS,
                            enable_aqueduct: enableAqueduct
                        }
                    })
                });

                const data = await response.json();

                if (data.status === 'success') {
                    statusText.textContent = data.iterations ? `✓ Completed in ${data.iterations} iteration(s)` : '✓ Done';
                    addMessage(data.response, 'assistant', data.tools_used, data.iterations);
                } else {
                    addMessage('Error: ' + data.error, 'assistant');
                    statusText.textContent = '✗ Error occurred';
                }
            } catch (error) {
                addMessage('Error: ' + error.message, 'assistant');
                statusText.textContent = '✗ Connection error';
            } finally {
                sendBtn.disabled = false;
            }
        }

        // Allow Enter key to send (Shift+Enter for new line)
        userInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""


def get_mcp_tools_list(mcp_url):
    """Fetch list of tools from an MCP server."""
    try:
        print(f"Fetching tools from {mcp_url}")
        response = requests.get(f"{mcp_url}/mcp/tools/list", timeout=10)
        response.raise_for_status()
        data = response.json()
        tools = data.get('tools', [])
        print(f"  Received {len(tools)} tools")
        return tools
    except Exception as e:
        print(f"  Error fetching tools from {mcp_url}: {e}")
        return []


def convert_mcp_tools_to_openai_format(mcp_tools, server_name):
    """
    Convert MCP tool definitions to OpenAI function calling format.

    MCP format: {name, description, inputSchema}
    OpenAI format: {type: "function", function: {name, description, parameters}}
    """
    openai_tools = []

    for tool in mcp_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": f"{server_name}_{tool['name']}",  # Prefix with server name
                "description": tool.get('description', ''),
                "parameters": tool.get('inputSchema', {
                    "type": "object",
                    "properties": {},
                    "required": []
                })
            }
        }
        openai_tools.append(openai_tool)

    return openai_tools


def get_all_tools_as_openai_format(enable_viirs=True, enable_aqueduct=True):
    """Fetch all MCP tools and convert to OpenAI function calling format."""
    all_tools = []

    if enable_viirs:
        viirs_tools = get_mcp_tools_list(VIIRS_MCP_URL)
        viirs_openai = convert_mcp_tools_to_openai_format(viirs_tools, "viirs")
        all_tools.extend(viirs_openai)
        print(f"Added {len(viirs_openai)} VIIRS tools")

    if enable_aqueduct:
        aqueduct_tools = get_mcp_tools_list(AQUEDUCT_MCP_URL)
        aqueduct_openai = convert_mcp_tools_to_openai_format(aqueduct_tools, "aqueduct")
        all_tools.extend(aqueduct_openai)
        print(f"Added {len(aqueduct_openai)} Aqueduct tools")

    print(f"Total tools available: {len(all_tools)}")
    return all_tools


def execute_mcp_tool(tool_name, tool_args):
    """
    Execute an MCP tool by calling the appropriate server.
    Tool names are prefixed: "viirs_query_recent_fires" or "aqueduct_list_datasets"
    """
    try:
        # Determine server based on prefix
        if tool_name.startswith("viirs_"):
            server_url = VIIRS_MCP_URL
            actual_tool_name = tool_name[6:]  # Remove "viirs_" prefix
        elif tool_name.startswith("aqueduct_"):
            server_url = AQUEDUCT_MCP_URL
            actual_tool_name = tool_name[9:]  # Remove "aqueduct_" prefix
        else:
            return json.dumps({"error": f"Unknown tool prefix: {tool_name}"})

        print(f"  Executing {tool_name} on {server_url}")
        print(f"    Args: {json.dumps(tool_args, indent=2)}")

        # Call the MCP server
        payload = {
            "tool": actual_tool_name,
            "arguments": tool_args
        }

        response = requests.post(
            f"{server_url}/mcp/call_tool",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        # Extract the result content
        if "result" in result:
            content_items = result["result"]
            if content_items and len(content_items) > 0:
                text_result = content_items[0].get("text", json.dumps(result))
                print(f"    Result: {text_result[:200]}...")
                return text_result

        # Fallback: return full result as JSON
        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        error_result = {
            "error": str(e),
            "tool": tool_name,
            "args": tool_args
        }
        print(f"    ERROR: {e}")
        return json.dumps(error_result)


def chat_with_climategpt(question, enable_viirs=True, enable_aqueduct=True, max_iterations=MAX_ITERATIONS):
    """
    Chat with ClimateGPT using MCP tool calling loop.
    Returns: (final_answer, iterations_used, tools_used)
    """
    print("\n" + "="*60)
    print(f"Starting MCP Tool Calling Chat")
    print(f"Question: {question}")
    print(f"VIIRS: {enable_viirs}, Aqueduct: {enable_aqueduct}")
    print("="*60)

    # Get available tools
    tools = get_all_tools_as_openai_format(enable_viirs, enable_aqueduct)

    if not tools:
        print("WARNING: No tools available! Sending query without tools.")
        messages = [
            {"role": "system", "content": "You are a helpful climate science assistant."},
            {"role": "user", "content": question}
        ]

        try:
            response = requests.post(
                CLIMATEGPT_URL,
                auth=(CLIMATEGPT_USER, CLIMATEGPT_PASS),
                json={
                    "model": CLIMATEGPT_MODEL,
                    "messages": messages
                },
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            return answer, 0, []
        except Exception as e:
            return f"Error: {str(e)}", 0, []

    # Initialize conversation with system message and user question
    messages = [
        {
            "role": "system",
            "content": "You are a helpful climate science assistant with access to fire detection data (VIIRS) and water risk data (Aqueduct). Use the available tools to answer questions with specific data and facts."
        },
        {"role": "user", "content": question}
    ]

    tools_used = []

    # Tool calling loop
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1} ---")

        try:
            # Send request to ClimateGPT with tools
            payload = {
                "model": CLIMATEGPT_MODEL,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }

            response = requests.post(
                CLIMATEGPT_URL,
                auth=(CLIMATEGPT_USER, CLIMATEGPT_PASS),
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

        except Exception as e:
            print(f"ERROR calling ClimateGPT: {e}")
            return f"Error connecting to ClimateGPT: {str(e)}", iteration, tools_used

        # Get assistant's response
        assistant_message = data["choices"][0]["message"]
        finish_reason = data["choices"][0]["finish_reason"]

        print(f"Finish reason: {finish_reason}")

        # Add assistant message to conversation
        messages.append(assistant_message)

        # Check if tools were called
        tool_calls = assistant_message.get("tool_calls", [])

        if tool_calls:
            print(f"ClimateGPT called {len(tool_calls)} tool(s)")

            # Execute each tool
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args_str = tool_call["function"]["arguments"]

                try:
                    tool_args = json.loads(tool_args_str) if tool_args_str else {}
                except json.JSONDecodeError:
                    tool_args = {}

                print(f"  Tool: {tool_name}")

                # Track tool usage
                tools_used.append({
                    "name": tool_name,
                    "args": tool_args
                })

                # Execute the tool
                result = execute_mcp_tool(tool_name, tool_args)

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result
                })

            # Continue loop to send tool results back
            continue

        else:
            # No tool calls - this is the final answer
            final_answer = assistant_message.get("content", "")
            print(f"\n✓ Final answer received (iteration {iteration + 1})")
            print(f"✓ Tools used: {len(tools_used)}")
            return final_answer, iteration + 1, tools_used

    # Max iterations reached
    print("\n⚠ Max iterations reached!")
    final_answer = assistant_message.get("content", "Max iterations reached without final answer")
    return final_answer, max_iterations, tools_used


@app.route('/')
def index():
    """Serve the main chat UI"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files like background images"""
    return send_from_directory(os.path.dirname(__file__), filename)


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests with MCP tool calling."""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        mcp_config = data.get('mcp_config', {
            'enable_viirs': True,
            'enable_aqueduct': True
        })

        if not user_message:
            return jsonify({
                'status': 'error',
                'error': 'No message provided'
            }), 400

        # Get MCP configuration
        enable_viirs = mcp_config.get('enable_viirs', True)
        enable_aqueduct = mcp_config.get('enable_aqueduct', True)

        # Chat with ClimateGPT using tool calling
        answer, iterations, tools_used = chat_with_climategpt(
            user_message,
            enable_viirs=enable_viirs,
            enable_aqueduct=enable_aqueduct
        )

        return jsonify({
            'status': 'success',
            'response': answer,
            'iterations': iterations,
            'tools_used': tools_used
        })

    except Exception as e:
        print(f"ERROR in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': f'Server error: {str(e)}'
        }), 500


if __name__ == '__main__':
    port = 5000
    print("\n" + "="*60)
    print("ClimateGPT Chat UI v3 - MCP Tool Calling")
    print("="*60)
    print(f"Web UI: http://127.0.0.1:{port}")
    print(f"\nMCP Servers:")
    print(f"  VIIRS:    {VIIRS_MCP_URL}")
    print(f"  Aqueduct: {AQUEDUCT_MCP_URL}")
    print(f"\nMax tool calling iterations: {MAX_ITERATIONS}")
    print("\nHow it works:")
    print("  1. Fetches tool definitions from MCP servers")
    print("  2. Sends tools to ClimateGPT in OpenAI format")
    print("  3. ClimateGPT decides which tools to call")
    print("  4. Tools are executed and results sent back")
    print("  5. Repeats until ClimateGPT has final answer")
    print("="*60 + "\n")

    app.run(host='127.0.0.1', port=port, debug=False)



