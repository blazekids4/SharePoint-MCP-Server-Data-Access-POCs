# Vantiva MCP Server

A production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives GitHub Copilot direct access to SharePoint content via the Microsoft Graph API. Hosted on **Azure Container Apps** for enterprise-scale deployment with centralized secrets management, auto-scaling, and zero local dependencies.

Built with Python and [FastMCP](https://github.com/jlowin/fastmcp).

---

## Architecture

The server runs as a **containerized HTTP service** on Azure Container Apps, eliminating the need for Python installations or local secrets management on developer machines.

```
┌──────────────────────┐       HTTPS          ┌─────────────────────────┐
│  VS Code + Copilot   │ ──────────────────► │  Azure Container Apps   │
│  (any developer)     │                      │  (vantiva-mcp-server)   │
└──────────────────────┘                      └───────────┬─────────────┘
                                                          │ HTTPS
                                                          ▼
                                              ┌──────────────────────────┐
                                              │ Microsoft Graph API      │
                                              │ (SharePoint + OneDrive)  │
                                              └──────────────────────────┘
```

**Key benefits:**
- **Zero local setup** — developers only need a URL in their VS Code MCP settings
- **Centralized secrets** — credentials stored in Azure Container Apps, not on developer machines
- **Auto-scaling** — scales from 1–3 replicas based on load
- **Centralized logging** — all tool invocations logged in Azure Log Analytics
- **One-command deployment** — `azd deploy` rebuilds and redeploys the entire stack

---

## What It Does

The server exposes SharePoint tools that Copilot automatically invokes based on natural language queries.

### Available Tools

| Tool | Description |
|---|---|
| `greet` | Returns a friendly greeting. Useful for testing server connectivity. |
| `add_numbers` | Adds two numbers. Simple health check tool. |
| `get_sharepoint_page` | Fetches content from a SharePoint page by site and page name. |
| `list_sharepoint_pages` | Lists all pages in a SharePoint site. |
| `search_sharepoint` | Searches for files in a SharePoint site's Documents library. |
| `list_sharepoint_folder` | Lists files and subfolders in a SharePoint document library. |
| `get_sharepoint_file_content` | Reads text content from files (.txt, .md, .json, .csv, .xml, .html, .pdf) in SharePoint. |

---

## Prerequisites

- **Azure subscription** with permissions to create resource groups and deploy Container Apps
- **Azure Developer CLI (`azd`)** — [Install here](https://aka.ms/azd-install)
- **Docker** (for local testing only, not required for deployment)
- **VS Code** with **GitHub Copilot** and **GitHub Copilot Chat** extensions
- A **Microsoft Entra ID (Azure AD) app registration** with client credentials

---

## Deployment

### 1. Clone the Repository

```bash
git clone <repo-url>
cd vantiva-mcp-server
```

### 2. Configure Entra ID App Registration

1. Go to [Azure Portal → App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade) and create a new registration.
2. Under **API permissions**, add **Application** permissions for **Microsoft Graph**:
   - `Sites.Read.All` (read SharePoint site content)
   - `Files.Read.All` (read files from document libraries)
3. Click **Grant admin consent** for your tenant.
4. Under **Certificates & secrets**, create a **client secret** and save the value.
5. Copy the **Application (client) ID** and **Directory (tenant) ID**.

### 3. Initialize Azure Environment

```bash
azd init
```

When prompted:
- **Environment name**: Choose a short name (e.g., `prod`, `dev`, or `vantivamcp`)
- This creates `.azure/<environment-name>/.env` for your deployment settings

### 4. Set Environment Variables

```bash
azd env set SHAREPOINT_TENANT_ID <your-tenant-id>
azd env set SHAREPOINT_CLIENT_ID <your-client-id>
azd env set SHAREPOINT_CLIENT_SECRET <your-client-secret>
azd env set SHAREPOINT_HOST <yourtenant.sharepoint.com>
```

These values are securely stored in Azure Container Apps secrets and never committed to source control.

### 5. Deploy to Azure

```bash
azd up
```

This single command:
1. Creates a resource group (`rg-vantiva-mcp` or similar)
2. Provisions a Container Apps Environment, Container Registry, and Log Analytics workspace
3. Builds the Docker image and pushes to Azure Container Registry
4. Deploys the Container App with secrets and environment variables
5. Outputs the MCP endpoint URL

**Example output:**
```
✓ Deploying service api to Azure...
  Container App URL: https://vantiva-mcp-4cqr7kxpw4idy.azurecontainerapps.io

SUCCESS: Your application was provisioned and deployed to Azure.
```

### 6. Configure VS Code

Create or update `.vscode/mcp.json` with the deployed URL:

```json
{
  "servers": {
    "vantiva": {
      "type": "streamable-http",
      "url": "https://vantiva-mcp-<your-random-id>.azurecontainerapps.io"
    }
  }
}
```

Replace `<your-random-id>` with the actual hostname from the `azd up` output.

### 7. Verify in VS Code

1. Open the workspace in VS Code
2. Open Copilot Chat (Ctrl+Shift+I / Cmd+Shift+I)
3. Click the tools icon in the input box
4. Verify **"vantiva"** appears in the MCP server list
5. Test with: *"Say hello to me"* or *"What documents are in the DeveloperCentral SharePoint site?"*

---

## Redeployment

To update the server after making code changes:

```bash
azd deploy
```

This rebuilds the container image and redeploys the Container App without reprovisioning infrastructure.

---

## How It Works

### Request Flow

1. **Developer asks Copilot a question** in VS Code (e.g., *"What files are in the DeveloperCentral SharePoint site?"*)
2. **Copilot analyzes the prompt** and determines which tool to invoke based on tool descriptions
3. **VS Code sends an MCP request** over HTTPS to the Container App endpoint
4. **The server authenticates to Microsoft Graph** using client credentials stored in Azure secrets
5. **The server calls the Graph API** to fetch SharePoint data
6. **The result is returned to Copilot**, which formulates a natural language response

### Authentication

The server uses the **OAuth 2.0 client credentials flow** with Microsoft Graph. Credentials are stored as **Container Apps secrets** and injected as environment variables at runtime:

- `SHAREPOINT_TENANT_ID` — Entra ID tenant
- `SHAREPOINT_CLIENT_ID` — App registration client ID  
- `SHAREPOINT_CLIENT_SECRET` — Client secret (never in source control)
- `SHAREPOINT_HOST` — SharePoint tenant hostname

Authentication tokens are acquired on-demand and cached by the `msal` library for performance.

### Transport Mode

`server.py` supports two transport modes controlled by the `MCP_TRANSPORT` environment variable:

- **`stdio`** (default) — Local development, communicates over stdin/stdout
- **`streamable-http`** — Production, listens on HTTP port 8080 for JSON-RPC requests

The Azure deployment sets `MCP_TRANSPORT=streamable-http` and `PORT=8080`.

---

## Monitoring and Troubleshooting

### View Container Logs

```bash
# Follow live logs
az containerapp logs show \
  --name <your-container-app-name> \
  --resource-group <your-resource-group> \
  --type console \
  --follow

# Or use azd to get the resource names
azd env get-values
```

### Common Issues

| Issue | Solution |
|---|---|
| **Server not appearing in Copilot** | Verify the URL in `.vscode/mcp.json` matches your Container App hostname. Reload VS Code. |
| **`401 Unauthorized` from Graph API** | Check that admin consent was granted for `Sites.Read.All` and `Files.Read.All` API permissions. |
| **`404 Not Found` from Graph API** | Verify the `site_name` parameter matches the SharePoint site URL segment (e.g., `"DeveloperCentral"` not `"Developer Central"`). |
| **Container App not starting** | Check logs for missing environment variables or authentication errors. Verify secrets are set with `azd env list`. |
| **Tools not triggering** | Confirm the server is listed in VS Code's MCP server list (tools icon in chat input). Try rephrasing the prompt to match tool descriptions. |

### Test the MCP Endpoint

You can verify the server is responding using `curl`:

```bash
curl -X POST https://<your-container-app-url>/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

You should see an MCP initialization response with the server name and available tools.

---

## How to Use with Copilot

You don't invoke tools directly — **Copilot decides when to use them** based on your natural language prompt. Example prompts:

| Prompt | Tool Invoked |
|---|---|
| *"Say hello to Justin"* | `greet` |
| *"What is 125 + 389?"* | `add_numbers` |
| *"Show me the Home page from the Engineering SharePoint site"* | `get_sharepoint_page` |
| *"List all pages in the HR site"* | `list_sharepoint_pages` |
| *"Search DeveloperCentral for API documentation"* | `search_sharepoint` |
| *"What files are in the Documentation folder on DeveloperCentral?"* | `list_sharepoint_folder` |
| *"Read the REST API guide PDF from DeveloperCentral"* | `get_sharepoint_file_content` |

You can also reference tools explicitly with the `#` prefix: `#search_sharepoint find onboarding docs`

---

## Adding New Tools

To extend the server with custom functionality:

1. **Add a function** to `server.py` with the `@mcp.tool()` decorator:

```python
@mcp.tool()
def my_custom_tool(param1: str, param2: int = 10) -> str:
    """
    Brief description of what this tool does.
    
    Args:
        param1: Description of param1.
        param2: Description of param2 (optional).
    """
    # Your implementation here
    return "result"
```

2. **Test locally** (see Local Development section below)
3. **Deploy** with `azd deploy`

The new tool will appear in Copilot's tool list automatically.

---

## Local Development

For development and testing without deploying to Azure:

### 1. Create a Virtual Environment

```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env` File

Create a `.env` file in the project root:

```env
SHAREPOINT_TENANT_ID=<your-tenant-id>
SHAREPOINT_CLIENT_ID=<your-client-id>
SHAREPOINT_CLIENT_SECRET=<your-client-secret>
SHAREPOINT_HOST=<yourtenant.sharepoint.com>
```

> **Do not commit this file.** It's already in `.gitignore`.

### 4. Run Locally via stdio

Create `.vscode/mcp.json` for local stdio testing:

```json
{
  "servers": {
    "vantiva-local": {
      "type": "stdio",
      "command": "${workspaceFolder}/venv/Scripts/python.exe",
      "args": ["${workspaceFolder}/server.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

> On macOS/Linux, change the path to `${workspaceFolder}/venv/bin/python`.

Restart VS Code to load the server. It will run as a child process and communicate via stdin/stdout.

### 5. Test Changes Locally

Make changes to `server.py`, then reload the MCP server in VS Code (Command Palette → **MCP: Restart Server**).

---

## Alternative: Microsoft ODSP Remote Server

Microsoft provides a hosted MCP server for SharePoint (`odsp-remote`) that requires no infrastructure or code. It uses **delegated user authentication** (each developer signs in with their own account) and provides pre-built tools for SharePoint and OneDrive.

**Configuration example:**

```json
{
  "servers": {
    "odsp-remote": {
      "type": "streamable-http",
      "url": "https://agent365.svc.cloud.microsoft/agents/tenants/${input:tenant_id}/servers/mcp_ODSPRemoteServer"
    }
  },
  "inputs": [
    {
      "id": "tenant_id",
      "prompt": "Enter your Entra tenant ID:"
    }
  ]
}
```

**When to use:**
- Simpler setup, no Azure deployment required
- Want per-user permissions instead of app-only access
- Don't need custom tools or logic

**When to use this custom server instead:**
- Need custom tools or business logic
- Want to combine SharePoint with other data sources
- Require app-only authentication or centralized secrets
- Need full control over error handling and response formatting

See [`documentation/mcp-approaches-comparison.md`](documentation/mcp-approaches-comparison.md) for a detailed comparison.

---

## Project Structure

```
vantiva-mcp-server/
├── azure.yaml                           # Azure Developer CLI configuration
├── Dockerfile                           # Container image definition
├── requirements.txt                     # Python dependencies
├── server.py                            # MCP server with tool definitions
├── .env                                 # Local secrets (not committed)
├── .vscode/
│   └── mcp.json                         # VS Code MCP server configuration
├── poc-graph-api/
│   ├── infra/                           # Azure infrastructure (Bicep)
│   ├── main.bicep                       # Subscription-scoped deployment
│   ├── main.parameters.json             # Parameter mappings
│   └── modules/
│       └── containerapp.bicep           # Container App, Registry, Logs
├── documentation/                       # Deployment guides
│   ├── hosting-mcp-server-end-to-end.md
│   ├── mcp-approaches-comparison.md
│   ├── enterprise-deployment-guide.md
│   └── resources.md
└── venv/                                # Python virtual environment (local only)
```

---

## Additional Resources

- **[Full Deployment Guide](documentation/hosting-mcp-server-end-to-end.md)** — Step-by-step walkthrough of the Azure deployment process
- **[Approach Comparison](documentation/mcp-approaches-comparison.md)** — Custom server vs. Microsoft ODSP remote server
- **[Enterprise Deployment Guide](documentation/enterprise-deployment-guide.md)** — Multi-environment, CI/CD, and security best practices
- **[MCP Protocol Specification](https://modelcontextprotocol.io/)** — Official MCP documentation
- **[FastMCP Documentation](https://github.com/jlowin/fastmcp)** — Python MCP framework

---

## Contributing

To contribute or extend this server:

1. Fork the repository
2. Make changes in a feature branch
3. Test locally using the stdio transport
4. Submit a pull request with a description of your changes

---

## License

[MIT License](LICENSE) (or your preferred license)
