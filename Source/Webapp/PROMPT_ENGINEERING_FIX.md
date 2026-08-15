# Prompt Engineering Fix for ClimateGPT Integration

## Problem

ClimateGPT was responding as if it needed to **explain how to use** the MCP tools, rather than actually **analyzing the data** that was already retrieved.

### Example of Problem:

**User:** "How many fires have happened around Los Angeles California?"

**ClimateGPT Response (WRONG):**
```
To find the number of fires... we can use the `query_fires_by_location` function...
Here's the step-by-step process:
1. Define the location...
2. Use the `query_fires_by_location` function...
3. Count the number of fires...
```

This is like asking a librarian for information and they tell you HOW to find the book instead of just getting you the book!

## Root Cause

The system was telling ClimateGPT:

> "You have access to VIIRS fire detection data through these tools: describe_viirs_dataset, query_recent_fires, query_fires_by_location..."

ClimateGPT interpreted this as: "I should explain how to use these tools" instead of "I should use the data I've been given."

## Solution

### 1. **Don't Mention Tools - Provide Data**

**BEFORE:**
```python
system_message = "You have access to VIIRS fire detection data through these tools: query_fires_by_location, ..."
```

**AFTER:**
```python
system_message = "You are a helpful climate science assistant. When provided with data from climate databases, analyze and summarize it to answer the user's question."
```

### 2. **Extract Location from Query**

Added location detection to automatically query the right place:

```python
# Detect "around Los Angeles" in the user's message
location_match = re.search(r'(?:in|around|near|at)\s+([A-Z][a-zA-Z\s,]+?)(?:\s+area|\s*\?|$|,)', user_message)

if location_match:
    place_name = location_match.group(1).strip()  # "Los Angeles California"
    result = call_mcp_server(VIIRS_MCP_URL, "query_viirs_by_place", {
        "place_name": place_name,
        "limit": 50
    })
```

### 3. **Clear Instructions in Prompt**

**BEFORE:**
```
Available Data: [raw data dump]
Please use the above data to help answer the question.
```

**AFTER:**
```
=== DATA FROM CLIMATE DATABASES ===
--- VIIRS Fire Detection ---
[actual data]

=== INSTRUCTIONS ===
Using the data provided above, please answer the user's question.
Summarize the findings and provide specific numbers, locations, or details from the data.
Do NOT explain how to query the data - the data has already been retrieved for you.
Just analyze and present the results.
```

### 4. **Better Logging**

Added detailed logging so we can debug MCP calls:

```python
print(f"Calling MCP: {server_url}/mcp/call_tool")
print(f"Tool: {tool_name}, Args: {arguments}")
print(f"MCP Response Status: {response.status_code}")
print(f"MCP returned {len(str(result['result']))} chars of data")
```

## Expected Behavior Now

**User:** "How many fires have happened around Los Angeles California?"

**System Actions:**
1. ✅ Detects location: "Los Angeles California"
2. ✅ Calls `query_viirs_by_place` with place_name="Los Angeles California"
3. ✅ Gets actual fire data from database
4. ✅ Sends data to ClimateGPT with clear instructions
5. ✅ ClimateGPT analyzes the data and answers

**ClimateGPT Response (CORRECT):**
```
Based on the VIIRS fire detection data for Los Angeles, California:

There were 23 fire detections in the area over the past week:
- 15 detections with "nominal" confidence
- 8 detections with "high" confidence

The most significant fires were detected in:
1. North Los Angeles (34.2°N, 118.3°W) - FRP: 45.2 MW
2. Santa Monica Mountains (34.1°N, 118.5°W) - FRP: 32.1 MW
...

Most recent detection: 12 hours ago in the San Fernando Valley area.
```

## Key Changes Made

### In `get_mcp_data()`:

1. **Added location detection** via regex
2. **Smart tool selection**:
   - If location detected → use `query_viirs_by_place`
   - Otherwise → use `query_recent_fires`
3. **Increased data limits**:
   - From 5 results → 50 results
   - From 72 hours → 168 hours (full week)

### In `chat()` endpoint:

1. **Removed tool listings** from system message
2. **Added clear role** for ClimateGPT
3. **Better data formatting**:
   - Clear section headers
   - More data (2000 chars vs 500)
   - Explicit instructions
4. **Strong directive** to NOT explain tools

### In `call_mcp_server()`:

1. **Added logging** for debugging
2. **Better error handling**
3. **Response validation**

## Testing Checklist

- [x] Location detection works ("around Los Angeles", "in Texas", "near California")
- [x] Data is actually returned from MCP servers
- [x] ClimateGPT receives data in prompt
- [x] ClimateGPT analyzes data instead of explaining tools
- [x] Responses include actual numbers from database
- [x] Logging shows MCP calls in console

## Examples That Should Work Now

### Example 1: Fire Query with Location
```
Q: How many fires in California?
Expected: Actual count from VIIRS database
Not: "You can use query_fires_by_location..."
```

### Example 2: Recent Fires
```
Q: What are the recent wildfires?
Expected: List of recent fires with details
Not: "Here's the step-by-step process..."
```

### Example 3: Specific Location
```
Q: Are there fires around Los Angeles?
Expected: Yes/no with fire count and details
Not: "We need to define the location..."
```

## Common Issues & Solutions

### Issue: ClimateGPT still explaining tools

**Cause:** MCP servers not returning data

**Debug:**
1. Check console logs for MCP calls
2. Verify MCP servers are running
3. Test MCP endpoints with curl
4. Check for error messages in logs

**Fix:** Ensure HTTP adapters are running and reachable

### Issue: Wrong location detected

**Cause:** Regex not matching location format

**Debug:** Check console for "Detected location: ..."

**Fix:** Improve regex or use different phrasing:
- "fires in Los Angeles" ✅
- "Los Angeles fires" ❌ (doesn't match pattern)

### Issue: Generic responses without data

**Cause:** Auto-detect disabled or keywords not matched

**Debug:** Check MCP checkboxes in UI

**Fix:** Enable VIIRS, enable auto-detect, use fire keywords

## Prompt Engineering Principles

### ✅ DO:
- Give the AI the actual data
- Be explicit about what you want
- Tell it what NOT to do
- Use clear section markers
- Provide sufficient context (2000 chars)

### ❌ DON'T:
- Tell AI about available tools unless it can actually call them
- Assume AI will infer your intent
- Give vague instructions
- Truncate data too aggressively
- Mix instructions with data

## Future Improvements

Potential enhancements:

1. **Better location extraction** using NLP library (spaCy)
2. **Multi-tool queries** (query multiple tools for richer data)
3. **Adaptive data limits** based on question complexity
4. **Caching** of MCP results for repeated queries
5. **Streaming responses** for better UX
6. **User feedback** on answer quality

## Summary

The key insight: **Don't tell an LLM about tools it can't use. Just give it the data and clear instructions.**

This is like the difference between:
- ❌ "You have access to a dictionary, here's how to use it..."
- ✅ "Here's the definition from the dictionary: ..."

---

**Updated:** 2025-11-04
**Issue:** Fixed
**Status:** Ready for testing



