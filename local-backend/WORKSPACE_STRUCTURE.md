# Workspace Structure and File Management

## Overview

The Denker application uses a **workspace-first security model** where all file operations happen within a controlled workspace directory. This ensures security while enabling seamless file sharing between agents.

## Workspace Location

The workspace is located at:
- **Development**: `/tmp/denker_workspace/default/`
- **Production**: `$DENKER_MEMORY_DATA_PATH/../workspace/default/` (if env var is set)
- **Fallback**: System temp directory + `/denker_workspace/default/`

## Workspace Structure

```
workspace/default/
├── report.md           # All files stored directly in root
├── analysis.pdf        # No subdirectories - flat structure
├── chart.png          # Generated charts and visualizations
├── document.docx      # Created documents and reports  
└── workspace_metadata.json  # File registry and metadata
```

**Key Features:**
- **Flat Structure**: All files stored directly in workspace root (no subdirectories)
- **Auto-Cleanup**: Workspace cache automatically deleted when app shuts down
- **Consistent Location**: Always uses "default" session for predictable file locations

## File Creation Workflow

### For Agents (markdown-editor, creator, editor)

1. **All editing happens in workspace**: Agents can only create/edit files within the workspace directory
2. **Filename-only paths**: Agents work with simple filenames like `"report.md"` - stored directly in workspace root
3. **Automatic workspace resolution**: File paths are automatically resolved to `workspace/default/filename`

### For User-Requested Output Locations

When users want files in specific locations (like Downloads folder):

1. **Edit in workspace first**: All editing happens in `workspace/default/filename.md`
2. **Move after completion**: The filesystem tool moves the final file to the user's desired location
3. **Security maintained**: No direct editing outside workspace

### Example Workflow

```
User: "Create a report and save it to ~/Downloads/report.pdf"

1. markdown-editor creates: workspace/default/report.md
2. Agent edits content in: workspace/default/report.md  
3. Agent converts to PDF: workspace/default/report.pdf
4. filesystem moves final file: ~/Downloads/report.pdf
```

## File Discovery

### For Agents
- Use simple filenames: `"report.md"`, `"analysis.pdf"`
- Workspace manager automatically resolves paths to `workspace/default/filename`
- Cross-agent file sharing through workspace registry

### For Users
- Files appear in requested locations after completion
- Intermediate files remain in workspace during editing
- Workspace cache automatically cleaned up on app shutdown

## Auto-Cleanup Behavior

The workspace cache is automatically cleaned up when:
- Application shuts down normally
- Application receives termination signals (SIGTERM, SIGINT, SIGHUP)
- Backend coordinator is restarted

This prevents accumulation of temporary files and keeps the system clean.

## Migration from Old Sessions

The system automatically migrates files from old timestamp-based session directories (`denker_12345`) to the new consistent `default` workspace on startup, flattening any subdirectory structure.

## Security Benefits

1. **Contained operations**: All file operations happen in controlled workspace
2. **No path traversal**: Agents cannot access files outside workspace
3. **Flat structure**: No subdirectories prevent complex path manipulation
4. **Auto-cleanup**: Temporary files don't accumulate over time
5. **Audit trail**: All file operations logged and tracked
6. **Clean separation**: User files vs workspace files clearly separated

## Agent Instructions

All agents understand this workflow through their system instructions:

- **markdown-editor**: Creates files in workspace root, uses simple filenames
- **creator**: Writes content to workspace files (flat structure)
- **editor**: Edits existing workspace files (no subdirectories)
- **filesystem**: Handles final file movement to user locations

This ensures security while maintaining a smooth user experience and preventing file system clutter. 