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
        shorthand: string;
        name: string;
        cwd: string;
        job: string;
        is_current: boolean;
      }>;
    }>;
  }>;

  let output = "iTerm2 Panes:\n";
  output += "=".repeat(60) + "\n";

  if (data.current_shorthand) {
    output += `You are here: ${data.current_shorthand}\n`;
  }

  for (const window of windows) {
    output += `\n[Window ${window.index}]\n`;

    for (const tab of window.tabs) {
      output += `  [Tab ${tab.index}]\n`;

      for (const session of tab.sessions) {
        const marker = session.is_current ? " <-- YOU ARE HERE" : "";
        output += `    ${session.shorthand}${marker}\n`;
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
          name: "iterm2_side_pane",
          description:
            "Get the side pane in the current tab. Returns the pane to the right of the current pane, or the left if current is rightmost. Useful for interacting with an adjacent terminal pane.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
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
            "List all iTerm2 windows, tabs, and panes with their shorthand IDs (like t5p2), names, working directories, and running jobs. Shows which pane you are in. Use these shorthand IDs with other tools.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "iterm2_read_pane",
          description:
            "Read the screen buffer contents of a specific iTerm2 pane. Returns the visible text in the terminal.",
          inputSchema: {
            type: "object",
            properties: {
              session_id: {
                type: "string",
                description:
                  "The pane ID - use shorthand like 't5p2' (tab 5, pane 2) or 'w1t5p2' (window 1, tab 5, pane 2). Numbers are 1-based to match iTerm2's UI.",
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
        {
          name: "iterm2_send_text",
          description:
            "Send text/commands to an iTerm2 pane as if typed by the user. Can optionally press Enter after the text.",
          inputSchema: {
            type: "object",
            properties: {
              session_id: {
                type: "string",
                description:
                  "The pane ID - use shorthand like 't5p2' (tab 5, pane 2) or 'w1t5p2'. Numbers are 1-based.",
              },
              text: {
                type: "string",
                description: "The text or command to send to the pane.",
              },
              newline: {
                type: "boolean",
                description:
                  "Whether to press Enter after the text (default: true). Set to false to type text without executing.",
                default: true,
              },
            },
            required: ["session_id", "text"],
          },
        },
        {
          name: "iterm2_send_control_character",
          description:
            "Send control characters like Ctrl+C, Ctrl+D, Ctrl+Z, or Ctrl+L to an iTerm2 pane. Useful for interrupting processes or clearing the screen.",
          inputSchema: {
            type: "object",
            properties: {
              session_id: {
                type: "string",
                description:
                  "The pane ID - use shorthand like 't5p2' (tab 5, pane 2) or 'w1t5p2'. Numbers are 1-based.",
              },
              control: {
                type: "string",
                enum: ["c", "d", "z", "l"],
                description:
                  "The control character to send: 'c' for Ctrl+C (interrupt/SIGINT), 'd' for Ctrl+D (EOF/logout), 'z' for Ctrl+Z (suspend/SIGTSTP), 'l' for Ctrl+L (clear screen).",
              },
            },
            required: ["session_id", "control"],
          },
        },
        {
          name: "iterm2_split_pane",
          description:
            "Split an iTerm2 pane horizontally or vertically, creating a new pane. Returns the session ID of the newly created pane.",
          inputSchema: {
            type: "object",
            properties: {
              session_id: {
                type: "string",
                description:
                  "The pane ID - use shorthand like 't5p2' (tab 5, pane 2) or 'w1t5p2'. Numbers are 1-based.",
              },
              vertical: {
                type: "boolean",
                description:
                  "If true, split vertically (side by side). If false (default), split horizontally (top/bottom).",
                default: false,
              },
            },
            required: ["session_id"],
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
        case "iterm2_side_pane": {
          const result = await runPythonClient(["side-pane"]);

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

          let output = "Side Pane:\n";
          output += `- Shorthand: ${result.shorthand}\n`;
          output += `- Position: ${result.position} of current pane (${result.current_shorthand})\n`;
          output += `- Name: ${result.name || "(unnamed)"}\n`;
          output += `- Working Directory: ${result.cwd || "N/A"}\n`;
          output += `- Running Job: ${result.job || "N/A"}\n`;
          output += `- Location: Window ${location.window}, Tab ${location.tab}, Pane ${location.pane}\n`;

          return {
            content: [{ type: "text", text: output }],
          };
        }

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

          let output = `Pane Contents (${result.shorthand}):\n`;
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
          output += `- Shorthand: ${result.shorthand}\n`;
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

        case "iterm2_send_text": {
          const { session_id: sessionId, text, newline } = args as {
            session_id?: string;
            text?: string;
            newline?: boolean;
          };

          if (!sessionId) {
            throw new McpError(
              ErrorCode.InvalidParams,
              "session_id is required"
            );
          }

          if (!text) {
            throw new McpError(ErrorCode.InvalidParams, "text is required");
          }

          const pythonArgs = ["send-text", sessionId, text];
          if (newline === false) {
            pythonArgs.push("--no-newline");
          }

          const result = await runPythonClient(pythonArgs);

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

          let output = `Text sent to pane ${result.shorthand}:\n`;
          output += `- Text: "${result.text_sent}"\n`;
          output += `- Newline: ${result.newline ? "Yes (Enter pressed)" : "No"}`;

          return {
            content: [{ type: "text", text: output }],
          };
        }

        case "iterm2_send_control_character": {
          const { session_id: sessionId, control } = args as {
            session_id?: string;
            control?: string;
          };

          if (!sessionId) {
            throw new McpError(
              ErrorCode.InvalidParams,
              "session_id is required"
            );
          }

          if (!control) {
            throw new McpError(ErrorCode.InvalidParams, "control is required");
          }

          const result = await runPythonClient([
            "send-control",
            sessionId,
            control,
          ]);

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
                text: `Sent ${result.description} to pane ${result.shorthand}`,
              },
            ],
          };
        }

        case "iterm2_split_pane": {
          const { session_id: sessionId, vertical } = args as {
            session_id?: string;
            vertical?: boolean;
          };

          if (!sessionId) {
            throw new McpError(
              ErrorCode.InvalidParams,
              "session_id is required"
            );
          }

          const pythonArgs = ["split", sessionId];
          if (vertical === true) {
            pythonArgs.push("--vertical");
          }

          const result = await runPythonClient(pythonArgs);

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

          let output = `Pane split successfully!\n`;
          output += `- Original pane: ${result.original_shorthand}\n`;
          output += `- New pane ID: ${result.new_session_id}\n`;
          output += `- Direction: ${result.split_direction}\n`;
          output += `\nUse iterm2_list_panes to see the new pane's shorthand.`;

          return {
            content: [{ type: "text", text: output }],
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
