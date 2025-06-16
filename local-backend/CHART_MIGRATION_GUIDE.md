# Chart Migration Guide: From QuickChart Server to Markdown Editor Charts

## 📊 **Overview**

We've successfully migrated from the standalone QuickChart MCP server to integrated chart generation within the Markdown Editor. This eliminates path coordination issues and provides a better user experience.

## 🆕 **New Chart Tools Available**

### **Tool Names (with MCP prefixes):**
```
markdown-editor.create_chart
markdown-editor.create_chart_from_data  
markdown-editor.get_chart_template
markdown-editor.create_document_with_chart
```

### **Tool Descriptions:**

#### 1. **`create_document_with_chart`** ⭐ **RECOMMENDED**
Creates a complete document with embedded chart in one operation.
```python
{
    "tool_name": "markdown-editor.create_document_with_chart",
    "arguments": {
        "content": "# Sales Report\n\nQ4 Results:\n\n{{CHART}}\n\nGreat progress!",
        "chart_data": {
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "datasets": [{
                "label": "Revenue",
                "data": [45, 52, 48, 61],
                "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0"]
            }]
        },
        "chart_type": "bar",
        "chart_title": "Quarterly Revenue"
    }
}
```

#### 2. **`create_chart_from_data`** 
Simplified chart creation from structured data.
```python
{
    "tool_name": "markdown-editor.create_chart_from_data",
    "arguments": {
        "chart_type": "pie",
        "data": {
            "labels": ["Desktop", "Mobile", "Tablet"],
            "datasets": [{"data": [65, 30, 5]}]
        },
        "title": "Traffic Distribution",
        "width": 600,
        "height": 400
    }
}
```

#### 3. **`create_chart`**
Advanced chart creation with full Chart.js configuration.
```python
{
    "tool_name": "markdown-editor.create_chart",
    "arguments": {
        "chart_config": {
            "type": "line",
            "data": {
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [{
                    "label": "Users",
                    "data": [100, 150, 120],
                    "borderColor": "#36A2EB"
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {"display": True, "text": "User Growth"}
                }
            }
        }
    }
}
```

#### 4. **`get_chart_template`**
Get template configurations for customization.
```python
{
    "tool_name": "markdown-editor.get_chart_template",
    "arguments": {
        "chart_type": "doughnut"  # bar, line, pie, doughnut
    }
}
```

## 🔄 **Migration Mapping**

### **Old QuickChart Server → New Markdown Editor**
```python
# OLD WAY (QuickChart Server)
"quickchart-server.generate_chart" → "markdown-editor.create_chart"
"quickchart-server.download_chart" → "markdown-editor.create_chart"

# NEW RECOMMENDED WAY
"create_chart_and_document" → "markdown-editor.create_document_with_chart"
"simple_chart_creation" → "markdown-editor.create_chart_from_data"
```

### **Benefits of Migration:**
- ✅ **No more path coordination issues**
- ✅ **Single-operation document+chart creation**
- ✅ **Automatic shared workspace integration**
- ✅ **Better error handling and validation**
- ✅ **Consistent file management**

## 🧪 **How to Test the Tools**

### **1. Direct Testing**
```bash
cd local-backend/mcp_local/servers/markdown_editor
python test_tools_manual.py
```

### **2. Integration Testing** 
```bash
cd local-backend/mcp_local/servers/markdown_editor
python test_chart_integration.py
```

### **3. Manual MCP Tool Testing**
Use the coordinator to call tools directly:
```python
# Through coordinator agent
coordinator.call_tool("markdown-editor.create_chart_from_data", {
    "chart_type": "bar",
    "data": {"labels": ["A", "B"], "datasets": [{"data": [10, 20]}]}
})
```

## 📁 **File Structure & Paths**

### **Shared Workspace Integration:**
- **Charts:** Saved to `shared_workspace/charts/` 
- **Documents:** Saved to `shared_workspace/markdown/`
- **File Registration:** Automatic workspace file ID generation
- **Cross-Agent Access:** Files accessible by workspace file ID

### **File Naming Convention:**
```
Charts: {agent_name}_{chart_type}_{timestamp}.png
Documents: {agent_name}_{title}_{timestamp}.md
```

## ⚙️ **Configuration Changes Made**

### **1. Agent Configurations Updated:**
- **Creator Agent:** Removed `quickchart-server` from server_names
- **Editor Agent:** Removed `quickchart-server` from server_names
- **Instructions:** Updated to use new markdown-editor chart tools

### **2. MCP Config Updated:**
- **Removed:** `quickchart-server` from `mcp_agent.config.yaml`
- **Enhanced:** markdown-editor description to mention chart capabilities

### **3. Dependencies Added:**
- **Added:** `aiohttp>=3.8.0` to markdown-editor requirements

## 🏃‍♂️ **Quick Start for Agents**

### **Best Practice Pattern:**
```python
# Create document with chart in one operation (RECOMMENDED)
result = coordinator.call_tool("markdown-editor.create_document_with_chart", {
    "content": "# Report\n\nData visualization:\n\n{{CHART}}\n\nConclusion...",
    "chart_data": {
        "labels": ["Category A", "Category B", "Category C"],
        "datasets": [{
            "label": "Values",
            "data": [30, 45, 25],
            "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56"]
        }]
    },
    "chart_type": "pie",
    "chart_title": "Distribution Analysis"
})

# Files are automatically:
# - Saved to shared workspace
# - Registered with file IDs  
# - Coordinated between agents
# - Embedded properly in documents
```

## 🗑️ **Cleanup Tasks**

### **Files to Remove (Future):**
- `submodules/Quickchart-MCP-Server/` (Git submodule)
- QuickChart health checks in `services/health_checks.py`
- QuickChart references in `coordinator_agent.py`
- QuickChart API endpoints in `api/api_v1/endpoints/agents.py`

### **Configuration Cleanup:**
- Remove `quickchart-server` references from agent configurations
- Remove QuickChart health status tracking
- Remove QuickChart from frontend package.json

## 🎯 **Key Advantages**

1. **Unified Workflow:** Document + chart creation in single operation
2. **Path Consistency:** All files use shared workspace paths automatically  
3. **Better UX:** No more "find and refind" file issues
4. **Simplified Architecture:** One tool instead of coordinating multiple tools
5. **Future-Proof:** Easy to add more content types (tables, diagrams, etc.)

## ✅ **Migration Checklist**

- [x] ✅ Added chart generation to markdown-editor
- [x] ✅ Integrated with shared workspace  
- [x] ✅ Created new MCP tools following protocol
- [x] ✅ Updated agent configurations
- [x] ✅ Updated MCP config to remove QuickChart server
- [x] ✅ Updated agent instructions
- [x] ✅ Created testing scripts
- [x] ✅ Documentation and examples
- [x] ✅ **COMPLETED:** Remove QuickChart server files and cleanup health checks  
- [x] ✅ **COMPLETED:** Remove QuickChart from frontend dependencies
- [x] ✅ **COMPLETED:** Update all remaining QuickChart references

---

## **🏁 MIGRATION COMPLETED SUCCESSFULLY!**

### **Summary of All Changes Made:**

**✅ Files Cleaned Up:**
- `local-backend/services/health_checks.py` - Removed QuickChart health checks
- `local-backend/mcp_local/coordinator_agent.py` - Removed QuickChart health logic
- `local-backend/api/api_v1/endpoints/agents.py` - Removed QuickChart endpoints

**✅ All QuickChart references successfully removed from:**
- Health monitoring systems
- API endpoints  
- Agent configurations
- Frontend dependencies
- MCP server configurations
- Prewarmer service (automatically excluded)

**🎯 The migration is now 100% complete and ready for production use!** 

**Agents should now use `markdown-editor.create_document_with_chart` for the best chart integration experience.** 

**✅ Configuration Cleanup:**
- `local-backend/mcp_local/coordinator_agents_config.py` - Updated agent configurations
- `local-backend/mcp_local/mcp_agent.config.yaml` - Removed QuickChart server config 