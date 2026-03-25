# Hosting the SharePoint MCP Server on Azure — End-to-End Guide

This document walks through everything we did to take the SharePoint MCP Server from a local Python process running on a developer machine to a hosted service on Azure Container Apps that any developer can connect to from GitHub Copilot — no Python, no secrets, and no local setup required.

---

## Starting Point

We started with a local MCP server (`server.py`) that:

- Ran as a child process of VS Code via **stdio** transport
- Authenticated to SharePoint via **client credentials** stored in a local `.env` file
- Required every developer to have Python, a virtual environment, and the `.env` file on their machine

```
Developer Machine
├── VS Code + GitHub Copilot
├── Python 3.12 + venv
├── server.py (stdio transport)
└── .env (SHAREPOINT_TENANT_ID, CLIENT_ID, CLIENT_SECRET, HOST)
```

The original `mcp.json` configuration:

```json
{
  "servers": {
    "sharepoint-mcp": {
      "type": "stdio",
      "command": "${workspaceFolder}/venv/Scripts/python.exe",
      "args": ["${workspaceFolder}/server.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

This worked well for a single developer but didn't scale — every machine needed Python, dependencies, and secrets.

---

## Goal

Host the MCP server centrally on Azure so that:

1. Developers only need a URL in their `mcp.json` — no Python, no `.env`, no local dependencies
2. Secrets are managed in Azure, not on developer machines
3. The server auto-scales and has centralized logging
4. Redeployment is a single command (`azd deploy`)

---

## Step 1: Update `server.py` to Support HTTP Transport

The local server used `stdio` transport (communication over stdin/stdout). For remote hosting, we needed **streamable HTTP** transport, where the server listens on a port and accepts JSON-RPC requests over HTTP.

We updated `server.py` to read the transport mode from an environment variable, defaulting to `stdio` for local development:

```python
# Create the MCP server (name appears in VS Code when discovering tools)
transport = os.environ.get("MCP_TRANSPORT", "stdio")
mcp = FastMCP(
    "sharepoint-mcp",
    host="0.0.0.0" if transport == "streamable-http" else "127.0.0.1",
    port=int(os.environ.get("PORT", "8080")),
)
```

And at the bottom:

```python
if __name__ == "__main__":
    mcp.run(transport=transport)
```

Key decisions:
- **`MCP_TRANSPORT` environment variable** — defaults to `stdio` so local development is unchanged. Set to `streamable-http` in Azure.
- **`PORT` environment variable** — defaults to `8080`. Azure Container Apps routes traffic to this port.
- **`host="0.0.0.0"`** — binds to all interfaces when running as HTTP, required for container networking.

---

## Step 2: Create a `requirements.txt`

We pinned the Python dependencies needed for the container image:

```
mcp[cli]>=1.26.0
msal>=1.35.0
httpx>=0.28.0
uvicorn>=0.41.0
python-dotenv>=1.0.0
```

---

## Step 3: Create a `Dockerfile`

A minimal container image based on `python:3.12-slim`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8080

CMD ["python", "server.py"]
```

We tested this locally before deploying:

```bash
docker build -t sharepoint-mcp-server:test .
docker run -d --name mcp-test -p 8080:8080 \
  -e MCP_TRANSPORT=streamable-http \
  -e PORT=8080 \
  sharepoint-mcp-server:test
```

Verified the server responded to MCP protocol initialization:

```
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

---

## Step 4: Create Azure Infrastructure (Bicep + azd)

We used the **Azure Developer CLI (`azd`)** with **Bicep** infrastructure-as-code to define the deployment.

### Project structure

```
sharepoint-mcp-server/
├── azure.yaml                          # azd project config
├── Dockerfile                          # Container image definition
├── requirements.txt                    # Python dependencies
├── server.py                           # MCP server (updated)
└── infra/
    ├── main.bicep                      # Subscription-scoped deployment
    ├── main.parameters.json            # Parameter values from azd env
    └── modules/
        └── containerapp.bicep          # Container App + Registry + Logs
```

### `azure.yaml`

Tells `azd` this is a Python project hosted on Container Apps, using a Dockerfile:

```yaml
name: sharepoint-mcp-server
metadata:
  template: sharepoint-mcp-server

services:
  api:
    project: .
    language: py
    host: containerapp
    docker:
      path: ./Dockerfile
```

### `infra/main.bicep`

Subscription-scoped template that creates a resource group and delegates to the Container App module:

- Creates `rg-{environmentName}` resource group
- Passes SharePoint credentials as secure parameters
- Outputs the Container App URL and MCP endpoint

### `infra/modules/containerapp.bicep`

Defines four resources:

| Resource | Purpose |
|---|---|
| **Log Analytics workspace** | Collects container logs for monitoring |
| **Container Apps Environment** | Managed hosting environment for container apps |
| **Container Registry** | Stores the Docker image (`azd` pushes here during deploy) |
| **Container App** | Runs the MCP server with HTTP ingress on port 8080 |

Key configuration in the Container App:

- **Ingress**: External, HTTPS-only, targeting port 8080
- **Secrets**: SharePoint credentials stored as Container Apps secrets (not in env vars directly)
- **Environment variables**: `MCP_TRANSPORT=streamable-http`, `PORT=8080`, plus secrets via `secretRef`
- **Scale**: 1–3 replicas (always at least 1 running)
- **Tag**: `azd-service-name: api` so `azd deploy` knows which Container App to update

### `infra/main.parameters.json`

Maps `azd` environment variables to Bicep parameters:

```json
{
  "parameters": {
    "environmentName": { "value": "${AZURE_ENV_NAME}" },
    "location": { "value": "${AZURE_LOCATION}" },
    "sharepointTenantId": { "value": "${SHAREPOINT_TENANT_ID}" },
    "sharepointClientId": { "value": "${SHAREPOINT_CLIENT_ID}" },
    "sharepointClientSecret": { "value": "${SHAREPOINT_CLIENT_SECRET}" },
    "sharepointHost": { "value": "${SHAREPOINT_HOST}" }
  }
}
```

---

## Step 5: Configure and Deploy

### Set up the azd environment

```powershell
# Create a new azd environment
azd env new sharepoint-mcp

# Set the Azure region
azd env set AZURE_LOCATION eastus

# Set SharePoint credentials (from .env)
azd env set SHAREPOINT_TENANT_ID "your-tenant-id"
azd env set SHAREPOINT_CLIENT_ID "your-client-id"
azd env set SHAREPOINT_CLIENT_SECRET "your-client-secret"
azd env set SHAREPOINT_HOST "yourtenant.sharepoint.com"
```

### Preview the deployment

```powershell
azd provision --preview
```

This showed 5 resources would be created:

```
Create : Resource group             : rg-sharepoint-mcp
Create : Container App              : sharepoint-mcp-<unique-id>
Create : Container Apps Environment : cae-4cqr7kxpw4idy
Create : Container Registry         : cr4cqr7kxpw4idy
Create : Log Analytics workspace    : log-4cqr7kxpw4idy
```

### Deploy

```powershell
azd up
```

This command:
1. **Packages** — builds the Docker image from the Dockerfile
2. **Provisions** — creates all Azure resources from the Bicep templates
3. **Deploys** — pushes the image to the Container Registry and updates the Container App

Output:

```
Deploying services (azd deploy)
  (✓) Done: Deploying service api
  - Endpoint: https://<your-container-app-url>/
  - Endpoint: https://<your-container-app-url>/mcp
```

---

## Step 6: Verify the Deployment

We tested the live endpoint with an MCP protocol `initialize` request:

```powershell
$headers = @{ "Accept" = "application/json, text/event-stream" }
Invoke-RestMethod `
  -Uri "https://<your-container-app-url>/mcp" `
  -Method POST `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

Response:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26",
  "capabilities":{"tools":{"listChanged":false},...},
  "serverInfo":{"name":"sharepoint-mcp","version":"1.26.0"}}}
```

The server correctly responds with the MCP protocol handshake, listing all tool capabilities.

---

## Step 7: Update `mcp.json` for GitHub Copilot

We updated `.vscode/mcp.json` so the `sharepoint-mcp` server points to the Azure-hosted endpoint, and kept the local version as a fallback:

```json
{
  "servers": {
    "sharepoint-mcp": {
      "type": "streamable-http",
      "url": "https://<your-container-app-url>/mcp"
    },
    "sharepoint-mcp-local": {
      "type": "stdio",
      "command": "${workspaceFolder}/venv/Scripts/python.exe",
      "args": ["${workspaceFolder}/server.py"],
      "envFile": "${workspaceFolder}/.env"
    }
  }
}
```

Any developer can now use the hosted MCP server by adding just the `sharepoint-mcp` entry to their `mcp.json` — no Python, no `.env`, no setup.

---

## Architecture (Before and After)

### Before — Local stdio

```
Developer Machine
├── VS Code + Copilot
├── Python + venv + pip dependencies
├── server.py (stdio)
└── .env (secrets on disk)
```

### After — Azure Container Apps

```
Developer Machine                        Azure (rg-sharepoint-mcp)
├── VS Code + Copilot   ──HTTPS──►   ├── Container App (FastMCP, streamable-http)
└── mcp.json (URL only)               ├── Container Registry (Docker image)
                                       ├── Container Apps Environment
                                       ├── Log Analytics (centralized logging)
                                       └── Secrets (managed by Azure)
```

---

## Azure Resources Created

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `rg-sharepoint-mcp` | Logical container for all resources |
| Container App | `sharepoint-mcp-<unique-id>` | Runs the MCP server |
| Container Registry | `cr4cqr7kxpw4idy` | Stores the Docker image |
| Container Apps Environment | `cae-4cqr7kxpw4idy` | Managed runtime for the container |
| Log Analytics Workspace | `log-4cqr7kxpw4idy` | Centralized logging and monitoring |

---

## Day-2 Operations

### Redeploy after code changes

```powershell
azd deploy
```

This rebuilds the Docker image, pushes it to the Container Registry, and updates the Container App — typically completes in under a minute.

### View logs

```powershell
az containerapp logs show \
  --name sharepoint-mcp-<unique-id> \
  --resource-group rg-sharepoint-mcp \
  --follow
```

Or use Log Analytics in the Azure Portal for query-based log analysis.

### Update secrets

```powershell
azd env set SHAREPOINT_CLIENT_SECRET "new-secret-value"
azd provision
```

### Tear down

```powershell
azd down
```

This removes all Azure resources in the resource group.

---

## Key Takeaways

1. **Transport flexibility** — The same `server.py` supports both `stdio` (local) and `streamable-http` (remote) via the `MCP_TRANSPORT` environment variable.
2. **Infrastructure as Code** — All Azure resources are defined in Bicep, version-controlled, and repeatable.
3. **One-command deploy** — `azd up` handles build, provision, and deploy in a single command.
4. **Zero developer setup** — Connecting to the hosted server requires only a URL in `mcp.json`.
5. **Secrets in Azure** — SharePoint credentials are stored as Container Apps secrets, not on developer machines.
