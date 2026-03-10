# Vantiva MCP Server

A custom [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives GitHub Copilot direct access to SharePoint content via the Microsoft Graph API. Built with Python and [FastMCP](https://github.com/jlowin/fastmcp).

---

## What It Does

The server exposes tools that Copilot can call during a chat session. When you ask Copilot a question that requires SharePoint data, it automatically invokes the appropriate tool behind the scenes.

### Available Tools

| Tool | Description |
|---|---|
| `greet` | Returns a friendly greeting. Useful for testing that the server is running. |
| `add_numbers` | Adds two numbers. Another simple test tool. |
| `get_sharepoint_page` | Fetches the content of a specific SharePoint page by site and page name. |
| `list_sharepoint_pages` | Lists all pages in a SharePoint site. |
| `search_sharepoint` | Searches for files in a SharePoint site's Documents library. |
| `list_sharepoint_folder` | Lists files and subfolders in a SharePoint document library. |
| `get_sharepoint_file_content` | Reads the text content of a file (.txt, .md, .json, .csv, .xml, .html, etc.) from a SharePoint document library. |

---

## Prerequisites

- **Python 3.10+**
- **VS Code** with **GitHub Copilot** and **GitHub Copilot Chat** extensions
- A **Microsoft Entra ID (Azure AD) app registration** with client credentials (for SharePoint access)
- Access to the target SharePoint site(s)

---

## Setup

### 1. Clone the Repository

```bash
git clone <repo-url>
cd vantiva-mcp-server
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **Windows (CMD):** `.\venv\Scripts\activate.bat`
- **macOS / Linux:** `source venv/bin/activate`

### 3. Install Dependencies

```bash
pip install msal httpx mcp[cli]
```

> `msal` handles Entra ID authentication, `httpx` handles HTTP requests to the Graph API, and `mcp[cli]` provides the FastMCP framework.

### 4. Create the `.env` File

Create a `.env` file in the project root with your SharePoint / Entra ID credentials:

```env
SHAREPOINT_TENANT_ID=your-entra-tenant-id
SHAREPOINT_CLIENT_ID=your-app-registration-client-id
SHAREPOINT_CLIENT_SECRET=your-client-secret
SHAREPOINT_HOST=yourtenant.sharepoint.com
```

> **Do not commit this file.** It is already listed in `.gitignore`.

### 5. Register the Server in VS Code

The file `.vscode/mcp.json` tells VS Code how to start the MCP server. It should already be present:

```json
{
  "servers": {
    "vantiva": {
      "type": "stdio",
      "command": "${workspaceFolder}/venv/Scripts/python.exe",
      "args": ["${workspaceFolder}/server.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

> On macOS/Linux, change the `command` path to `${workspaceFolder}/venv/bin/python`.

### 6. Start the Server

Open the workspace in VS Code. The server starts automatically when Copilot discovers it through `mcp.json`. You can verify it's running by looking for **"vantiva"** in the MCP server list (click the tools icon in the Copilot Chat input box).

You can also start it manually via the command palette: **MCP: List Servers** → select **vantiva** → **Start**.

---

## Authentication

### How It Works

The server uses the **OAuth 2.0 client credentials flow** to authenticate with Microsoft Graph. This is an app-only flow — the server authenticates as an application, not as a specific user.

```
VS Code (stdio) → server.py → MSAL (client credentials) → Microsoft Graph API → SharePoint
```

1. When a tool is called, `server.py` uses the `msal` library to request an access token from Entra ID.
2. The token is acquired using the **tenant ID**, **client ID**, and **client secret** from your `.env` file.
3. The token is sent as a `Bearer` header to the Microsoft Graph API to access SharePoint data.

### Entra ID App Registration Setup

1. Go to [Azure Portal → App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade) and create a new registration.
2. Under **API permissions**, add the following **Application** permissions for **Microsoft Graph**:
   - `Sites.Read.All` (to read SharePoint site content)
   - `Files.Read.All` (to read files from document libraries)
3. Click **Grant admin consent** for your tenant.
4. Under **Certificates & secrets**, create a new **client secret** and copy the value into your `.env` file.
5. Copy the **Application (client) ID** and **Directory (tenant) ID** into your `.env` file.

---

## How It Works

### Architecture

The server runs as a **local child process** of VS Code, communicating over **stdio** (standard input/output). There is no network port exposed on your machine.

```
┌──────────────────────┐       stdio        ┌──────────────────┐
│  VS Code + Copilot   │ ◄──────────────► │   server.py      │
│  (sends tool calls)  │                    │   (FastMCP)      │
└──────────────────────┘                    └────────┬─────────┘
                                                     │ HTTPS
                                                     ▼
                                            ┌──────────────────┐
                                            │ Microsoft Graph  │
                                            │ API (SharePoint) │
                                            └──────────────────┘
```

1. **VS Code** reads `.vscode/mcp.json` and spawns `server.py` as a subprocess.
2. **Copilot** discovers the tools the server exposes (via the MCP protocol).
3. When you ask Copilot a question, it decides whether to invoke a tool based on the tool descriptions and your prompt.
4. The tool function runs, calls the Graph API if needed, and returns the result to Copilot.
5. Copilot uses the returned data to formulate its response.

### Tool Discovery

Copilot reads the tool names and docstrings from `server.py` to understand what each tool does and when to call it. The `@mcp.tool()` decorator registers a function as an MCP tool. The function's docstring and parameter type hints tell Copilot how and when to use it.

---

## How to Trigger Tools

You don't call tools directly — **Copilot decides when to use them** based on your natural language prompt. Here are example prompts that would trigger each tool:

| Prompt Example | Tool Triggered |
|---|---|
| *"Say hello to Justin"* | `greet` |
| *"What is 42 + 58?"* | `add_numbers` |
| *"Show me the Home page from the Engineering SharePoint site"* | `get_sharepoint_page` |
| *"List all pages in the HR site"* | `list_sharepoint_pages` |
| *"Search the DeveloperCentral site for API documentation"* | `search_sharepoint` |
| *"What files are in the API Documentation folder on DeveloperCentral?"* | `list_sharepoint_folder` |
| *"Read the REST API Guide from DeveloperCentral"* | `get_sharepoint_file_content` |

You can also mention the tool by name with the `#` prefix in Copilot Chat (e.g., `#search_sharepoint find onboarding docs`).

> **Tip:** If Copilot isn't using a tool you expect, check that the MCP server is running (look for the tools icon in the chat input) and rephrase your prompt to match the tool's description.

---

## Adding New Tools

To add a new tool, define a function in `server.py` with the `@mcp.tool()` decorator:

```python
@mcp.tool()
def my_new_tool(param1: str, param2: int = 10) -> str:
    """
    One-line description of what this tool does.
    
    Args:
        param1: Description of param1.
        param2: Description of param2.
    """
    # Your logic here
    return "result"
```

Restart the MCP server (or reload VS Code) to pick up the new tool.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Server not appearing in Copilot | Make sure `.vscode/mcp.json` is present and the Python path is correct. Reload VS Code. |
| `Auth failed` error | Verify your `.env` values. Ensure admin consent was granted for the app's API permissions. |
| `404` from Graph API | Double-check the `site_name` — it's the URL segment, not the display name (e.g., `"DeveloperCentral"` not `"Developer Central"`). |
| Tools not triggering | Confirm the server is started (check MCP server list). Try rephrasing your prompt or referencing the tool with `#`. |
| `ModuleNotFoundError` | Activate the virtual environment and run `pip install msal httpx mcp[cli]`. |

---

## Project Structure

```
vantiva-mcp-server/
├── .env                  # Entra ID credentials (not committed)
├── .gitignore
├── .vscode/
│   └── mcp.json          # VS Code MCP server configuration
├── server.py             # MCP server with tool definitions
├── server.json           # ODSP remote MCP server schema (separate)
├── documentation/        # Additional guides
│   ├── enterprise-deployment-guide.md
│   ├── mcp-approaches-comparison.md
│   └── resources.md
└── venv/                 # Python virtual environment (not committed)
```
