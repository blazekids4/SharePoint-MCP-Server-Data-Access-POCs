# Enterprise Deployment & Authentication Guide

How to deploy the custom MCP server across an organization and authenticate developers securely at scale.

---

## Deployment Models

There are three ways to deploy the custom MCP server. Each has different trade-offs for security, maintenance, and developer experience.

---

### Option 1: Local Per-Developer (Current Setup)

Each developer runs the MCP server as a local Python process on their own machine.

```
Developer Machine
├── VS Code + Copilot
├── Python + venv
├── server.py (stdio transport)
└── .env (credentials)
```

**How it works:**
- VS Code spawns `server.py` as a child process via stdio transport.
- The server runs only while VS Code is open.
- Each developer needs Python, the virtual environment, and credentials on their machine.

**Configuration (`.vscode/mcp.json`):**
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

| Pros | Cons |
|---|---|
| Simple to set up for small teams | Every developer needs Python + dependencies |
| No infrastructure to manage | Secrets stored locally on each machine |
| Works offline (after token acquisition) | Hard to update — must push changes to every machine |
| No network latency | No centralized logging or audit trail |

**Best for:** Small teams (< 20 developers), proof of concept, or rapid prototyping.

---

### Option 2: Centralized Remote Server (Recommended for Enterprise)

Host the MCP server as a web service that all developers connect to over HTTP. The server runs on company infrastructure — an internal VM, Kubernetes cluster, or cloud service.

```
Developer Machine                    Company Infrastructure
├── VS Code + Copilot  ──HTTP──►    ├── MCP Server (FastMCP)
└── mcp.json (URL only)             ├── Auth middleware (Entra ID)
                                    ├── SharePoint Graph API access
                                    └── Centralized logging
```

**How it works:**
- The MCP server runs as a persistent web service using streamable HTTP or SSE transport.
- Developers configure VS Code to connect to the server's URL.
- Authentication is handled by the server — developers sign in via Entra ID (Azure AD).
- No Python, no secrets, no dependencies on developer machines.

**Server code change** — switch transport from stdio to HTTP:
```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

**Developer configuration (`.vscode/mcp.json`):**
```json
{
  "servers": {
    "vantiva": {
      "type": "streamable-http",
      "url": "https://mcp.internal.yourcompany.com/mcp"
    }
  }
}
```

**Hosting options:**

| Platform | Notes |
|---|---|
| **Azure App Service** | Managed PaaS, easy SSL, supports Python, integrates with Entra ID for auth. |
| **Azure Container Apps** | Containerized, auto-scaling, good for microservices. |
| **Azure Kubernetes Service (AKS)** | Full control, best for orgs already running Kubernetes. |
| **Internal VM / Docker host** | Simple, behind corporate firewall. |
| **AWS ECS / GCP Cloud Run** | If not on Azure — but adds complexity for Graph API auth. |

| Pros | Cons |
|---|---|
| Zero setup on developer machines | Requires infrastructure to host and maintain |
| Centralized secret management | Network dependency — developers need connectivity |
| Centralized logging and audit trail | Adds latency vs. local process |
| Single place to update tools | Must handle availability / scaling |
| Enforce auth and access control at the server | SSL/TLS certificate management |

**Best for:** Enterprise teams (50+ developers), organizations with existing cloud infrastructure.

---

### Option 3: Cloud-Hosted Dev Environments

If developers use cloud-hosted development environments, the MCP server can run alongside their workspace — combining the simplicity of local with the control of centralized.

| Environment | How MCP Server Runs |
|---|---|
| **GitHub Codespaces** | Server starts automatically via devcontainer; uses managed identity or Codespace secrets for credentials. |
| **Azure Dev Box** | Server runs locally on the Dev Box; secrets injected via Azure Key Vault. |
| **VS Code Remote (SSH)** | Server runs on the remote host; credentials stored on the server, not the developer's laptop. |

**Best for:** Organizations already using cloud dev environments.

---

## Authentication Methods

How developers authenticate to the MCP server and how the server authenticates to SharePoint/Graph API are two separate concerns.

### Developer → MCP Server Authentication

How you verify which developer is making requests to the server.

---

#### Method A: No Auth (Stdio — Local Only)

With the local stdio deployment, the server runs as a child process of VS Code. There's no network exposure, so no authentication is needed between the developer and the server.

- **Security:** The server inherits the developer's OS session. Only that user can access it.
- **Risk:** Credentials (`.env` file) are stored on the developer's machine.
- **Use with:** Option 1 (Local Per-Developer).

---

#### Method B: Entra ID (Azure AD) OAuth2 — Recommended

The MCP server validates a bearer token issued by Microsoft Entra ID. Each developer signs in with their organizational account.

**Flow:**
1. VS Code prompts the developer to sign in via browser (Entra ID).
2. Copilot includes the access token in requests to the MCP server.
3. The server validates the token and extracts the user's identity.
4. (Optional) The server uses On-Behalf-Of (OBO) flow to call Graph API as that user.

**Server-side token validation example:**
```python
from fastapi import Request, HTTPException
import jwt
from jwt import PyJWKClient

TENANT_ID = "your-tenant-id"
CLIENT_ID = "your-mcp-server-app-id"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

jwks_client = PyJWKClient(JWKS_URL)

async def validate_token(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header.split(" ", 1)[1]
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    )
    return claims
```

| Pros | Cons |
|---|---|
| Per-user identity and audit trail | Requires Entra ID app registration |
| Can enforce group-based access (e.g., only "MCP Users" group) | Token validation adds complexity |
| Supports On-Behalf-Of for per-user SharePoint access | Developers must sign in |
| Industry-standard OAuth2 / OpenID Connect | |

**Use with:** Option 2 (Centralized Remote Server).

---

#### Method C: API Key / Shared Secret

The server requires a static API key in the request headers. All developers use the same key, or keys are issued per team.

**Developer configuration:**
```json
{
  "servers": {
    "vantiva": {
      "type": "streamable-http",
      "url": "https://mcp.internal.yourcompany.com/mcp",
      "headers": {
        "X-API-Key": "${input:mcp_api_key}"
      }
    }
  },
  "inputs": [
    {
      "id": "mcp_api_key",
      "type": "promptString",
      "description": "MCP server API key",
      "password": true
    }
  ]
}
```

| Pros | Cons |
|---|---|
| Simple to implement | No per-user identity — all requests look the same |
| Low overhead | Key rotation is painful at scale |
| | If the key leaks, everyone is compromised |
| | Cannot enforce per-user SharePoint permissions |

**Use with:** Small teams where simplicity outweighs security concerns. Not recommended for enterprise.

---

#### Method D: Mutual TLS (mTLS)

Each developer has a client certificate issued by the company's internal CA. The server validates the certificate on connection.

| Pros | Cons |
|---|---|
| Strong authentication without passwords | Certificate distribution and lifecycle management |
| Per-user identity via certificate subject | More complex infrastructure (internal CA) |
| No tokens to manage | Not natively supported by all MCP clients |

**Use with:** High-security environments with existing PKI infrastructure.

---

### MCP Server → SharePoint (Graph API) Authentication

How the server itself authenticates to Microsoft Graph to access SharePoint data.

---

#### Method 1: Client Credentials (App-Only) — Current Setup

The server uses a registered app's client ID and secret to get a token. All requests to Graph API use the same service principal identity.

```python
result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
```

- **SharePoint permissions:** Application-level (e.g., `Sites.Read.All`). The app can access all sites.
- **Identity:** Shared — every developer's request appears as the same service principal.
- **Secret storage:** Environment variable, Azure Key Vault, or managed identity.

**Risk:** The service principal typically has broad access. A developer using the MCP server could access SharePoint sites they wouldn't normally have access to in their browser.

---

#### Method 2: On-Behalf-Of (OBO) Flow — Recommended for Enterprise

The server exchanges the developer's Entra ID token for a Graph API token that acts as that user. SharePoint permissions are enforced per user.

```python
result = app.acquire_token_on_behalf_of(
    user_assertion=developer_access_token,
    scopes=["https://graph.microsoft.com/Sites.Read.All"],
)
```

- **SharePoint permissions:** Delegated — each developer can only access sites they have permission to.
- **Identity:** Per-user — audit logs show which developer accessed what.
- **Requires:** The developer to authenticate to the MCP server via Entra ID (Method B above).

**This is the gold standard for enterprise** — it combines per-user authentication with per-user SharePoint access control.

---

#### Method 3: Managed Identity (Azure-Hosted Only)

If the MCP server runs on Azure (App Service, Container Apps, AKS), it can use a managed identity to authenticate to Graph API — no secrets at all.

```python
from azure.identity import ManagedIdentityCredential

credential = ManagedIdentityCredential()
token = credential.get_token("https://graph.microsoft.com/.default")
```

- **SharePoint permissions:** Application-level (like client credentials), but no secret to manage.
- **Secret storage:** None — Azure handles the credential lifecycle.
- **Combine with OBO** for per-user access: use managed identity as the app credential, then OBO to act as the user.

---

## Recommended Enterprise Architecture

For an organization with hundreds of developers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Machines                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ VS Code      │  │ VS Code      │  │ VS Code      │ ...  │
│  │ + Copilot    │  │ + Copilot    │  │ + Copilot    │      │
│  │ mcp.json     │  │ mcp.json     │  │ mcp.json     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │ HTTPS           │ HTTPS           │ HTTPS         │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure App Service / Container Apps              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  MCP Server (FastMCP, streamable-http)                 │  │
│  │  ├── Entra ID token validation (developer auth)       │  │
│  │  ├── OBO flow (per-user Graph API access)             │  │
│  │  ├── Scoped tools (DeveloperCentral site only)        │  │
│  │  └── Centralized logging (App Insights)               │  │
│  └────────────────────────────────────────────────────────┘  │
│  Managed Identity (no secrets stored)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ Graph API (OBO token)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Microsoft Graph API                             │
│  └── SharePoint Online (per-user permissions enforced)      │
└─────────────────────────────────────────────────────────────┘
```

### Key decisions:

| Decision | Recommendation |
|---|---|
| **Hosting** | Azure App Service or Container Apps |
| **Developer auth** | Entra ID OAuth2 (Method B) |
| **Graph API auth** | Managed Identity + OBO flow (Method 3 + Method 2) |
| **Secret management** | None needed — managed identity eliminates secrets |
| **Site scoping** | Tools hardcoded or configured for specific sites |
| **Logging** | Azure Application Insights |
| **Access control** | Entra ID security group (e.g., "MCP Users") |
| **Distribution** | Share `mcp.json` via repo template or VS Code settings sync |

### Entra ID App Registration Setup

You need **one** app registration for the MCP server:

1. **App Registration** — Create in Azure Portal → App Registrations.
2. **API Permissions** — Add `Microsoft Graph` → Delegated → `Sites.Read.All` (or scoped to specific sites via `Sites.Selected`).
3. **Expose an API** — Define a scope (e.g., `api://<app-id>/MCP.Access`) so developers can consent.
4. **Authentication** — Add a redirect URI for the OAuth2 flow.
5. **Security Group** — (Optional) Restrict access by requiring group membership in the app's "Users and groups" assignment.

### Developer Onboarding Checklist

For each developer:

1. Install VS Code with GitHub Copilot.
2. Add the `mcp.json` configuration (provided by the team).
3. Sign in with their organizational Entra ID account when prompted.
4. Done — no Python, no secrets, no local setup.

---

## Comparison Summary

| Factor | Local (stdio) | Centralized (HTTP) + Entra + OBO |
|---|---|---|
| Developer setup | Python + venv + .env | mcp.json + sign-in |
| Secrets on dev machines | Yes (client secret) | No |
| Per-user SharePoint permissions | No | Yes (OBO) |
| Audit trail | No | Yes (per-user identity) |
| Site scoping | Yes | Yes |
| Centralized updates | No (push to each machine) | Yes (update server once) |
| Uptime dependency | None (local process) | Server must be available |
| Cost | Free (runs locally) | Hosting costs (App Service, etc.) |
| Scalability | N/A (per-machine) | Scales with hosting platform |
