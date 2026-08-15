#!/usr/bin/env node

/**
 * MCP HTTP Client
 * Bridges Claude Desktop's stdio-based MCP protocol to HTTP-based MCP servers
 */

const http = require('http');
const https = require('https');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

// Get server URL from command line
const serverUrl = process.argv[2];
if (!serverUrl) {
  process.stderr.write('Usage: node mcp-http-client.js <server-url>\n');
  process.exit(1);
}

const url = new URL(serverUrl);
const isHttps = url.protocol === 'https:';
const httpLib = isHttps ? https : http;

// Debug logging to file (not stderr to avoid interfering with JSON-RPC)
const logFile = path.join(process.env.TEMP || '/tmp', `mcp-http-client-${url.port}.log`);
function debugLog(msg) {
  const timestamp = new Date().toISOString();
  fs.appendFileSync(logFile, `${timestamp} ${msg}\n`);
}

// Setup readline for JSON-RPC over stdio
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

// Helper function to make HTTP requests
function makeRequest(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: path,
      method: method,
      headers: {
        'Content-Type': 'application/json'
      }
    };

    const req = httpLib.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          resolve(json);
        } catch (e) {
          reject(new Error(`Invalid JSON response: ${body}`));
        }
      });
    });

    req.on('error', (e) => reject(e));

    if (data) {
      req.write(JSON.stringify(data));
    }
    req.end();
  });
}

debugLog(`MCP HTTP Client starting for ${serverUrl}`);

// Handle incoming JSON-RPC messages from Claude Desktop
rl.on('line', async (line) => {
  let messageId = null;
  try {
    const message = JSON.parse(line);
    messageId = message.id;
    debugLog(`Received: ${message.method} (id: ${messageId})`);

    // Handle different JSON-RPC methods
    switch (message.method) {
      case 'initialize':
        // Return MCP server capabilities
        const initResponse = {
          jsonrpc: '2.0',
          id: message.id,
          result: {
            protocolVersion: '2024-11-05',
            capabilities: {
              tools: {}
            },
            serverInfo: {
              name: 'mcp-http-bridge',
              version: '1.0.0'
            }
          }
        };
        console.log(JSON.stringify(initResponse));
        break;

      case 'tools/list':
        // Fetch tools from HTTP server
        try {
          debugLog('Fetching tools list from HTTP server');
          const toolsData = await makeRequest('GET', '/mcp/tools/list');
          debugLog(`Received ${toolsData.tools?.length || 0} tools`);
          const response = {
            jsonrpc: '2.0',
            id: message.id,
            result: {
              tools: toolsData.tools || []
            }
          };
          console.log(JSON.stringify(response));
        } catch (e) {
          debugLog(`tools/list error: ${e.message}`);
          const errorResponse = {
            jsonrpc: '2.0',
            id: message.id,
            error: {
              code: -32603,
              message: `Failed to list tools: ${e.message}`
            }
          };
          console.log(JSON.stringify(errorResponse));
        }
        break;

      case 'tools/call':
        // Call a tool via HTTP
        try {
          const { name, arguments: args } = message.params;
          debugLog(`Calling tool: ${name}`);
          const resultData = await makeRequest('POST', '/mcp/call_tool', {
            tool: name,
            arguments: args || {}
          });

          debugLog(`Tool ${name} returned successfully`);
          const response = {
            jsonrpc: '2.0',
            id: message.id,
            result: {
              content: resultData.result || resultData.content || []
            }
          };
          console.log(JSON.stringify(response));
        } catch (e) {
          debugLog(`Tool call error (${name}): ${e.message}`);
          const errorResponse = {
            jsonrpc: '2.0',
            id: message.id,
            error: {
              code: -32603,
              message: `Tool call failed: ${e.message}`
            }
          };
          console.log(JSON.stringify(errorResponse));
        }
        break;

      default:
        // Unknown method - only send error if we have a message id
        if (message.id !== undefined) {
          const errorResponse = {
            jsonrpc: '2.0',
            id: message.id,
            error: {
              code: -32601,
              message: `Method not found: ${message.method}`
            }
          };
          console.log(JSON.stringify(errorResponse));
        }
    }
  } catch (e) {
    // Parse error - send error response if we have an id
    if (messageId !== null && messageId !== undefined) {
      const errorResponse = {
        jsonrpc: '2.0',
        id: messageId,
        error: {
          code: -32700,
          message: `Parse error: ${e.message}`
        }
      };
      console.log(JSON.stringify(errorResponse));
    }
  }
});

rl.on('close', () => {
  process.exit(0);
});

// Handle process termination
process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));
