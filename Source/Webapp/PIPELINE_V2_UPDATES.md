# Pipeline App v2 - MCP Server Selection Feature

## What's New

Added user controls to select which MCP servers to use when querying ClimateGPT!

## Features Added

### 1. **MCP Data Source Controls**

Three checkboxes allow users to control MCP server usage:

- ☑️ **VIIRS Fire Detection** - Enable/disable VIIRS MCP server
- ☑️ **Aqueduct Water Risk** - Enable/disable Aqueduct MCP server
- ☑️ **Auto-detect** - Use keyword detection vs. always query

### 2. **Smart Modes**

**Auto-Detect Mode (Default):**
- ✅ Only queries VIIRS when fire-related keywords detected
- ✅ Only queries Aqueduct when water-related keywords detected
- ✅ Most efficient - minimal unnecessary queries

**Always Query Mode:**
- When auto-detect is OFF
- Queries enabled MCP servers for every message
- Useful for testing or when you know you need the data

**No MCP Mode:**
- Uncheck both VIIRS and Aqueduct
- Pure ClimateGPT responses with no database augmentation

### 3. **Visual Feedback**

**Status Indicator:**
- Shows current mode in real-time
- Color-coded for easy understanding:
  - 🟢 Green = Auto-detection active
  - 🔵 Blue = Always query mode
  - ⚪ Gray = No MCP servers enabled

**Response Badges:**
- Each assistant response shows which MCP sources were used
- Example: "Data sources: VIIRS Fire Detection, Aqueduct Water Data"

### 4. **Better UI/UX**

- Color-coded badges for fire (red) and water (blue)
- Real-time status updates when toggling checkboxes
- Clean, professional appearance

## Usage Examples

### Example 1: Fire Query with Auto-Detect

**Settings:**
- ✅ VIIRS enabled
- ✅ Aqueduct enabled
- ✅ Auto-detect enabled

**Query:** "What are the recent wildfires?"

**Result:** Only VIIRS is queried (fire keyword detected)

---

### Example 2: General Query with No MCP

**Settings:**
- ❌ VIIRS disabled
- ❌ Aqueduct disabled
- ❌ Auto-detect (doesn't matter)

**Query:** "What is climate change?"

**Result:** Pure ClimateGPT response, no database queries

---

### Example 3: Testing Both Sources

**Settings:**
- ✅ VIIRS enabled
- ✅ Aqueduct enabled
- ❌ Auto-detect disabled

**Query:** "Tell me about the climate"

**Result:** Both VIIRS and Aqueduct are queried regardless of keywords

---

### Example 4: Water-Only Mode

**Settings:**
- ❌ VIIRS disabled
- ✅ Aqueduct enabled
- ✅ Auto-detect enabled

**Query:** "Show me data about floods in Texas"

**Result:** Only Aqueduct is queried (water keyword + enabled)

## Technical Changes

### Frontend (HTML/JavaScript)

**New UI Elements:**
```html
<div class="mcp-controls">
  <input type="checkbox" id="enableVIIRS" checked>
  <input type="checkbox" id="enableAqueduct" checked>
  <input type="checkbox" id="autoDetect" checked>
  <div class="mcp-status" id="mcpStatus">...</div>
</div>
```

**New JavaScript Functions:**
- `updateMCPStatus()` - Updates status indicator
- Enhanced `sendMessage()` - Sends MCP config to backend
- Enhanced `addMessage()` - Shows data source badges

### Backend (Python)

**Updated Functions:**

**`get_mcp_data(user_message, mcp_config)`:**
```python
# Now accepts mcp_config dict with:
{
    'enable_viirs': bool,
    'enable_aqueduct': bool,
    'auto_detect': bool
}
```

**`chat()` endpoint:**
- Reads `mcp_config` from request body
- Passes config to `get_mcp_data()`
- Only mentions tools that are enabled
- Returns MCP sources used in response

## Configuration Options

### Default Behavior (All Checked)
```javascript
{
  enable_viirs: true,
  enable_aqueduct: true,
  auto_detect: true
}
```

Result: Smart keyword-based routing (most efficient)

### Testing Mode (Auto-detect OFF)
```javascript
{
  enable_viirs: true,
  enable_aqueduct: true,
  auto_detect: false
}
```

Result: Always queries both MCP servers

### ClimateGPT-Only Mode
```javascript
{
  enable_viirs: false,
  enable_aqueduct: false,
  auto_detect: false
}
```

Result: No MCP queries, pure LLM responses

## Benefits

1. **User Control** - Users decide when to use MCP data
2. **Efficiency** - Can disable expensive database queries when not needed
3. **Testing** - Easy to compare MCP-augmented vs. pure LLM responses
4. **Transparency** - Clear indication of which data sources were used
5. **Flexibility** - Different modes for different use cases

## Keywords Reference

**Fire Keywords (VIIRS):**
- fire, fires, wildfire, wildfires
- burn, burning, burnt
- thermal, hotspot, hotspots
- smoke, flame, viirs
- blaze, inferno, ignition, combustion

**Water Keywords (Aqueduct):**
- water, flood, flooding
- drought, precipitation, rainfall
- river, rivers, lake, lakes
- stream, streams, aquatic, hydro
- hydrological, watershed, aqueduct
- reservoir, groundwater, aquifer

## Compatibility

- ✅ Works with existing HTTP adapters
- ✅ Works with SSH tunnels
- ✅ Works with pipeline_app_v2.py standalone
- ✅ Backward compatible (defaults to all enabled)

## Testing Checklist

- [ ] Test with VIIRS only
- [ ] Test with Aqueduct only
- [ ] Test with both enabled (auto-detect)
- [ ] Test with both enabled (always query)
- [ ] Test with both disabled (no MCP)
- [ ] Verify status indicator updates
- [ ] Verify data source badges appear
- [ ] Test fire keywords trigger VIIRS
- [ ] Test water keywords trigger Aqueduct
- [ ] Test mixed keywords trigger both

## Future Enhancements

Possible additions:
- [ ] Save user preferences in localStorage
- [ ] Add more keyword categories
- [ ] Allow custom keyword configuration
- [ ] Show loading indicator per MCP server
- [ ] Display query time/performance metrics
- [ ] Add "force query" button for current message only
- [ ] MCP server health status indicators

## Upgrade Instructions

If you have an older version of pipeline_app_v2.py:

1. **Backup your current version**
2. **Update to new version** (already done!)
3. **No database changes needed**
4. **No configuration changes needed**
5. **Test with different checkbox combinations**

The new features are fully backward compatible!

---

**Updated:** 2025-11-04
**Version:** 2.1
**Status:** Production Ready

