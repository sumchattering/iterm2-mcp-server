# iTerm2 MCP Server

An MCP (Model Context Protocol) server that allows AI assistants like Claude to read the contents of iTerm2 terminal panes. This enables AI assistants to see what's happening in your other terminal windows and tabs.

## Features

- **List all panes**: See all open iTerm2 windows, tabs, and panes with their working directories and running jobs
- **Read pane contents**: Get the screen buffer text from any pane
- **Current pane detection**: Automatically detects which pane the server is running in
- **Status checking**: Verify that iTerm2 Python API is properly configured

## Prerequisites

1. **macOS** with iTerm2 installed
2. **Node.js** >= 18.0.0
3. **Python 3** with the `iterm2` package:
   ```bash
   pip install iterm2
   ```
4. **iTerm2 Python API enabled**:
   - Open iTerm2 > Settings (Cmd+,)
   - Go to **General** > **Magic**
   - Check **Enable Python API**
   - Restart iTerm2

## Installation

### Using npx (recommended)

```bash
npx iterm2-mcp-server
```

### Global installation

```bash
npm install -g iterm2-mcp-server
iterm2-mcp-server
```

## Configuration

### Claude Desktop

Add to your Claude Desktop configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "iterm2": {
      "command": "npx",
      "args": ["iterm2-mcp-server"]
    }
  }
}
```

### Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "iterm2": {
      "command": "npx",
      "args": ["iterm2-mcp-server"]
    }
  }
}
```

## Available Tools

### `iterm2_status`

Check if iTerm2 Python API is properly configured and ready to use.

### `iterm2_list_panes`

List all iTerm2 windows, tabs, and panes with their:
- Session IDs
- Names
- Working directories
- Running jobs
- Which pane is current (marked with `<-- CURRENT`)

### `iterm2_read_pane`

Read the screen buffer contents of a specific pane by its session ID.

**Parameters:**
- `session_id` (required): The session ID of the pane to read (e.g., `w0t0p0:ABC123...`)

### `iterm2_current_pane`

Get information about the current iTerm2 pane where the MCP server is running.

### `iterm2_enable_api`

Enable the iTerm2 Python API in preferences. Note: iTerm2 must be restarted after enabling.

## Example Usage

Once configured, you can ask Claude:

- "What's running in my other terminal tabs?"
- "Can you see the output from my npm server in the other pane?"
- "Read the contents of the terminal running my Python script"
- "List all my open terminal panes"

## Troubleshooting

### "Connection failed" error

1. Make sure iTerm2 is running
2. Verify Python API is enabled: iTerm2 > Settings > General > Magic > Enable Python API
3. **Restart iTerm2** after enabling the API (Cmd+Q, then reopen)

### "iterm2 module not installed"

Install the Python package:
```bash
pip install iterm2
```

### "Not running in an iTerm2 session"

The MCP server needs to be started from within an iTerm2 terminal for current pane detection to work.

## How It Works

This MCP server uses the [iTerm2 Python API](https://iterm2.com/python-api/) to communicate with iTerm2 via a WebSocket connection. The server:

1. Receives tool calls from the AI assistant via MCP
2. Executes Python scripts that use the `iterm2` library
3. Returns formatted results back to the assistant

## Development

```bash
# Clone the repository
git clone https://github.com/sumchattering/iterm2-mcp-server.git
cd iterm2-mcp-server

# Install dependencies
npm install

# Build
npm run build

# Run locally
npm start
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
