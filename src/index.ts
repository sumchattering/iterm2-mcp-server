#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ErrorCode,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Path to the Python client script
const PYTHON_CLIENT = join(__dirname, "..", "python", "iterm2_client.py");

interface PythonResult {
  error?: string;
  message?: string;
  [key: string]: unknown;
}

/**
 * Execute the Python iTerm2 client and return parsed JSON result
 */
async function runPythonClient(
  args: string[]
): Promise<PythonResult> {
  return new Promise((resolve, reject) => {
    const childProcess = spawn("python3", [PYTHON_CLIENT, ...args], {
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    childProcess.stdout.on("data", (data: Buffer) => {
      stdout += data.toString();
    });

    childProcess.stderr.on("data", (data: Buffer) => {
      stderr += data.toString();
    });

    childProcess.on("close", (code: number | null) => {
      if (stdout) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch {
          reject(new Error(`Failed to parse Python output: ${stdout}`));
        }
      } else if (stderr) {
        reject(new Error(stderr));
      } else if (code !== 0) {
        reject(new Error(`Python process exited with code ${code}`));
      } else {
        reject(new Error("No output from Python process"));
      }
    });

    childProcess.on("error", (err: Error) => {
      reject(err);
    });
  });
}

/**
 * Format pane list for human-readable output
 */
function formatPaneList(data: PythonResult): string {
  const windows = data.windows as Array<{
    index: number;
    id: string;
    tabs: Array<{
      index: number;
      id: string;
      sessions: Array<{
        index: number;
        id: string;
        name: string;
        cwd: string;
        job: string;
        is_current: boolean;
      }>;
    }>;
  }>;

  let output = "iTerm2 Panes:\n";
  output += "=".repeat(60) + "\n";

  if (data.current_session_id) {
    output += `Current session: ${data.current_session_id}\n`;
  }

  for (const window of windows) {
    output += `\n[Window ${window.index}]\n`;

    for (const tab of window.tabs) {
      output += `  [Tab ${tab.index}]\n`;

      for (const session of tab.sessions) {
        const marker = session.is_current ? " <-- CURRENT" : "";
        output += `    [Pane ${session.index}] ${session.id}${marker}\n`;
        if (session.name) output += `      Name: ${session.name}\n`;
        if (session.cwd) output += `      CWD:  ${session.cwd}\n`;
        if (session.job) output += `      Job:  ${session.job}\n`;
      }
    }
  }

  return output;
}

/**
 * Create and configure the MCP server
 */
function createServer(): Server {
  const server = new Server(
    {
      name: "iterm2-mcp-server",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: "iterm2_status",
          description:
            "Check if iTerm2 Python API is properly configured and ready to use",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "iterm2_list_panes",
          description:
            "List all iTerm2 windows, tabs, and panes with their session IDs, names, working directories, and running jobs. Shows which pane is the current one.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "iterm2_read_pane",
          description:
            "Read the screen buffer contents of a specific iTerm2 pane by its session ID. Returns the visible text in the terminal.",
          inputSchema: {
            type: "object",
            properties: {
              session_id: {
                type: "string",
                description:
                  "The session ID of the pane to read (e.g., 'w0t0p0:ABC123...'). Use iterm2_list_panes to find session IDs.",
              },
            },
            required: ["session_id"],
          },
        },
        {
          name: "iterm2_current_pane",
          description:
            "Get information about the current iTerm2 pane where the MCP server is running",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "iterm2_enable_api",
          description:
            "Enable the iTerm2 Python API in preferences. Note: iTerm2 must be restarted after enabling.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
      ],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case "iterm2_status": {
          const result = await runPythonClient(["status"]);

          if (result.error) {
            return {
              content: [
                {
                  type: "text",
                  text: `Error: ${result.message}`,
                },
              ],
            };
          }

          let status = "iTerm2 API Status:\n";
          status += `- Python iterm2 module: ${result.iterm2_module_installed ? "Installed" : "NOT INSTALLED"}\n`;
          status += `- API enabled in preferences: ${result.api_enabled ? "Yes" : "No"}\n`;
          status += `- Running in iTerm2: ${result.in_iterm_session ? "Yes" : "No"}\n`;
          status += `- Ready to use: ${result.ready ? "Yes" : "No"}\n`;

          if (!result.iterm2_module_installed) {
            status += "\nTo install the iterm2 module: pip install iterm2";
          }
          if (!result.api_enabled) {
            status +=
              "\nTo enable the API: Use iterm2_enable_api tool, then restart iTerm2";
          }

          return {
            content: [{ type: "text", text: status }],
          };
        }

        case "iterm2_list_panes": {
          const result = await runPythonClient(["list"]);

          if (result.error) {
            return {
              content: [
                {
                  type: "text",
                  text: `Error: ${result.message}`,
                },
              ],
            };
          }

          return {
            content: [
              {
                type: "text",
                text: formatPaneList(result),
              },
            ],
          };
        }

        case "iterm2_read_pane": {
          const sessionId = (args as { session_id?: string })?.session_id;

          if (!sessionId) {
            throw new McpError(
              ErrorCode.InvalidParams,
              "session_id is required"
            );
          }

          const result = await runPythonClient(["read", sessionId]);

          if (result.error) {
            return {
              content: [
                {
                  type: "text",
                  text: `Error: ${result.message}`,
                },
              ],
            };
          }

          let output = `Pane Contents (${result.session_id}):\n`;
          output += "=".repeat(60) + "\n";
          if (result.name) output += `Name: ${result.name}\n`;
          if (result.cwd) output += `CWD: ${result.cwd}\n`;
          output += "=".repeat(60) + "\n\n";
          output += result.contents as string;

          return {
            content: [{ type: "text", text: output }],
          };
        }

        case "iterm2_current_pane": {
          const result = await runPythonClient(["current"]);

          if (result.error) {
            return {
              content: [
                {
                  type: "text",
                  text: `Error: ${result.message}`,
                },
              ],
            };
          }

          const location = result.location as {
            window: number;
            tab: number;
            pane: number;
          };

          let output = "Current Pane:\n";
          output += `- Session ID: ${result.session_id}\n`;
          output += `- Name: ${result.name || "(unnamed)"}\n`;
          output += `- Working Directory: ${result.cwd || "N/A"}\n`;
          output += `- Running Job: ${result.job || "N/A"}\n`;
          output += `- Location: Window ${location.window}, Tab ${location.tab}, Pane ${location.pane}\n`;

          return {
            content: [{ type: "text", text: output }],
          };
        }

        case "iterm2_enable_api": {
          const result = await runPythonClient(["enable"]);

          if (result.error) {
            return {
              content: [
                {
                  type: "text",
                  text: `Error: ${result.message}`,
                },
              ],
            };
          }

          return {
            content: [
              {
                type: "text",
                text: result.message as string,
              },
            ],
          };
        }

        default:
          throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
      }
    } catch (error) {
      if (error instanceof McpError) {
        throw error;
      }

      const errorMessage =
        error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text",
            text: `Error: ${errorMessage}`,
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}

/**
 * Main entry point
 */
async function main(): Promise<void> {
  const server = createServer();
  const transport = new StdioServerTransport();

  await server.connect(transport);

  // Handle graceful shutdown
  process.on("SIGINT", async () => {
    await server.close();
    process.exit(0);
  });

  process.on("SIGTERM", async () => {
    await server.close();
    process.exit(0);
  });
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
