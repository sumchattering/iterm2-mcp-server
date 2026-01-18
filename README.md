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

Add the MCP server using the CLI:

```bash
claude mcp add --scope user iterm2 -- npx github:sumchattering/iterm2-mcp-server
```

This installs it globally so it's available in all your projects. You can verify it's working:

```bash
claude mcp list
```

You should see: `iterm2: npx github:sumchattering/iterm2-mcp-server - ✓ Connected`

## Available Tools

### `iterm2_list_panes`

List all iTerm2 windows, tabs, and panes with their shorthand IDs, names, working directories, and running jobs.

### `iterm2_read_pane`

Read the screen buffer contents of a specific pane.

**Parameters:**
- `session_id` (required): The pane ID using shorthand like `t3p1` (tab 3, pane 1) or `w1t3p1`

### `iterm2_send_text`

Send text or commands to an iTerm2 pane as if typed by the user.

**Parameters:**
- `session_id` (required): The pane ID (e.g., `t3p1`)
- `text` (required): The text or command to send
- `newline` (optional, default: true): Whether to press Enter after the text

### `iterm2_send_control_character`

Send control characters like Ctrl+C, Ctrl+D, Ctrl+Z, or Ctrl+L to an iTerm2 pane.

**Parameters:**
- `session_id` (required): The pane ID (e.g., `t3p1`)
- `control` (required): `c` (Ctrl+C), `d` (Ctrl+D), `z` (Ctrl+Z), `l` (Ctrl+L)

### `iterm2_split_pane`

Split an iTerm2 pane horizontally or vertically, creating a new pane.

**Parameters:**
- `session_id` (required): The pane ID to split (e.g., `t3p1`)
- `vertical` (optional, default: false): If true, split vertically (side by side)

### `iterm2_current_pane`

Get information about the current iTerm2 pane where Claude Code is running.

### `iterm2_status`

Check if iTerm2 Python API is properly configured and ready to use.

### `iterm2_enable_api`

Enable the iTerm2 Python API in preferences. Note: iTerm2 must be restarted after enabling.

## Pane IDs

Panes are identified using shorthand IDs that match iTerm2's UI (1-based indexing):

- `t3p1` - Tab 3, Pane 1 (assumes Window 1)
- `t3p2` - Tab 3, Pane 2
- `w1t3p1` - Window 1, Tab 3, Pane 1 (explicit window)
- `w2t1p1` - Window 2, Tab 1, Pane 1

Use `iterm2_list_panes` to see all available panes and their IDs.

## Using with Claude Code

Once installed, Claude Code can see and interact with your terminal panes. Here are effective ways to use it:

### Asking about panes

- "What's in tab 3?" - Claude will read the contents of tab 3
- "What's running in the pane next to you?" - Claude can identify adjacent panes
- "Show me all my terminal tabs" - Lists all panes with their shorthand IDs
- "What's the output of my server?" - Claude can find and read server output

### Running commands in other panes

- "Run `npm test` in t3p1" - Sends command to specific pane
- "Stop the process in tab 4" - Sends Ctrl+C to interrupt
- "Clear the terminal in t2p1" - Sends Ctrl+L

### Working with multiple panes

- "Split my terminal and run the dev server in the new pane"
- "What errors are showing in my other terminals?"
- "Compare the output in tab 2 and tab 3"

### Tips for effective queries

1. **Be specific about location**: "tab 3" or "t3p1" is clearer than "the other terminal"
2. **Reference the pane list**: Ask Claude to list panes first if you're unsure of the layout
3. **Use relative references**: "the pane next to you" or "the tab on the left" work too

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

## Future Improvements

The following features are being considered for future releases. Feedback welcome!

- **Create tab/window**: `iterm2_create_tab` and `iterm2_create_window` tools
- **Close pane**: `iterm2_close_pane` tool to close panes programmatically
- **Focus pane**: `iterm2_focus_pane` to bring a specific pane to the foreground
- **Wait for prompt**: `iterm2_wait_for_prompt` to wait until a command finishes executing
- **Set pane title**: Ability to set custom titles for panes
- **Performance optimization**: Persistent Python process instead of spawning per request
