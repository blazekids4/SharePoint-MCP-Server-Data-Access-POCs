# MCP Server Approaches: Custom Local vs. Microsoft Remote

## Overview

There are two distinct ways to give GitHub Copilot access to SharePoint data via the Model Context Protocol (MCP). This document compares the **custom local server** (`server.py`) with the **Microsoft-hosted remote server** (`odsp-remote` via `server.json`) and provides guidance for enterprise-scale adoption.

---

## Approach 1: Custom Local MCP Server (`server.py`)

### How It Works

- A Python-based MCP server runs **locally on each developer's machine** via stdio transport.
- Authenticates using **app-only client credentials** (Azure AD app registration with a client ID and client secret).
- Calls the Microsoft Graph API directly with custom code you write and maintain.
- Every tool (`search_sharepoint`, `list_sharepoint_folder`, `get_sharepoint_file_content`, etc.) is defined in your codebase.

### Configuration

```json
// .vscode/mcp.json
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

Requires a `.env` file with:

```
SHAREPOINT_TENANT_ID=<your-tenant-id>
SHAREPOINT_CLIENT_ID=<your-client-id>
SHAREPOINT_CLIENT_SECRET=<your-client-secret>
SHAREPOINT_HOST=yourtenant.sharepoint.com
```

### Pros

- **Full control** over tool behavior, filtering, error handling, and response formatting.
- **Extensible** — add any custom tool (non-SharePoint tools, internal APIs, business logic).
- **No dependency** on Microsoft's MCP platform availability or feature set.
- Can **combine multiple data sources** in a single server.

### Cons

- **Secret management burden** — every developer needs access to a client secret (or per-developer app registrations).
- **App-only permissions** — operates as a service principal, not as the individual user. Cannot enforce per-user access controls natively.
- **Maintenance overhead** — you own the code, including updates when the Graph API evolves.
- **Local runtime dependency** — requires Python, dependencies, and a virtual environment on each machine.
- **No audit trail per user** — all requests use the same service principal identity.

---

## Approach 2: Microsoft-Hosted Remote MCP Server (`odsp-remote`)

### How It Works

- The MCP server runs on **Microsoft's infrastructure** (`agent365.svc.cloud.microsoft`).
- VS Code connects via **streamable HTTP** transport directly to Microsoft's endpoint.
- Authentication uses **delegated user credentials** — each developer signs in with their own Microsoft Entra (Azure AD) account via interactive browser auth.
- Tools are **pre-built and maintained by Microsoft** — no custom code required.

### Configuration

```json
// .vscode/mcp.json
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
      "type": "promptString",
      "description": "Your Microsoft Entra tenant ID"
    }
  ]
}
```

No `.env` file, no secrets, no app registration needed.

### Pros

- **Zero code to maintain** — Microsoft builds and updates the tools.
- **Delegated auth** — each developer authenticates as themselves, so SharePoint permissions are enforced per user.
- **No secrets to distribute** — no client IDs or secrets; uses standard Entra ID sign-in.
- **No local runtime** — no Python, no virtual environment, no dependencies.
- **Audit trail** — requests are tied to individual user identities.
- **Automatic updates** — Microsoft can add new tools or fix bugs without any action on your part.

### Cons

- **Limited to Microsoft's tool set** — you can only use the tools Microsoft provides (e.g., `findSite`, `getFolderChildren`, `readSmallTextFile`).
- **No custom logic** — cannot add business rules, combine data sources, or create non-SharePoint tools.
- **Platform dependency** — requires your tenant to be enrolled/supported on Microsoft's MCP platform.
- **Potential latency** — requests go through Microsoft's cloud infrastructure rather than running locally.
- **Feature lag** — if you need a capability Microsoft hasn't built yet, you must wait for them to add it.

---

## Side-by-Side Comparison

| Dimension | Custom Local (`server.py`) | Microsoft Remote (`odsp-remote`) |
|---|---|---|
| **Hosting** | Developer's machine | Microsoft cloud |
| **Transport** | stdio | Streamable HTTP |
| **Authentication** | App-only (client secret) | Delegated (user sign-in) |
| **Permissions model** | Service principal (shared identity) | Per-user (individual identity) |
| **Setup per developer** | Python + venv + `.env` with secrets | Just provide tenant ID + sign in |
| **Tools** | Custom, you write and maintain | Pre-built by Microsoft |
| **Extensibility** | Unlimited | Limited to Microsoft's offerings |
| **Secret management** | Required (client ID + secret) | Not required |
| **Maintenance** | You own it | Microsoft owns it |
| **Audit / compliance** | Shared identity, harder to audit | Per-user identity, full audit trail |
| **Offline capability** | Works without internet (if Graph cached) | Requires internet |

---

## Enterprise Recommendation: Hundreds of Developers

For an organization with **hundreds of developers**, the two approaches serve different roles. The best strategy is typically a **hybrid model**.

### Use the Remote Server as the Default for SharePoint Access

For standard SharePoint operations (browsing sites, reading documents, searching files), the **Microsoft remote server is the clear winner at scale**:

1. **Zero deployment friction** — No Python environment, no virtual environments, no dependency management across hundreds of machines. Developers add one JSON block to their VS Code settings and sign in.

2. **No secret sprawl** — Distributing a client secret to hundreds of developers is a security risk. If the secret leaks, it provides app-level access to SharePoint. The remote server eliminates this entirely — each developer authenticates with their own credentials.

3. **Per-user permissions** — The remote server respects each user's SharePoint permissions. Developer A only sees sites they have access to. With the custom server's app-only credentials, every developer has the same (typically broad) access regardless of their actual SharePoint permissions.

4. **Compliance and auditing** — Every request is tied to an individual user identity, making it easy to meet compliance requirements. With a shared service principal, you cannot distinguish who accessed what.

5. **Zero maintenance** — No code updates, no dependency upgrades, no Graph API version migrations. Microsoft handles all of this.

### Keep the Custom Server for Extended Capabilities

The custom local server remains valuable for:

- **Non-SharePoint tools** — Internal APIs, custom business logic, developer utilities (like `greet` or `add_numbers`), or tools that combine multiple data sources.
- **Custom data transformations** — If you need to process or filter SharePoint data in specific ways before returning it to Copilot.
- **Capabilities the remote server doesn't offer** — If Microsoft's tool set has gaps for your workflow.

### Recommended Hybrid Configuration

```json
{
  "servers": {
    "vantiva-custom": {
      "type": "stdio",
      "command": "python",
      "args": ["server.py"],
      "envFile": ".env"
    },
    "odsp-remote": {
      "type": "streamable-http",
      "url": "https://agent365.svc.cloud.microsoft/agents/tenants/${input:tenant_id}/servers/mcp_ODSPRemoteServer"
    }
  },
  "inputs": [
    {
      "id": "tenant_id",
      "type": "promptString",
      "description": "Your Microsoft Entra tenant ID"
    }
  ]
}
```

In this model:
- **Remove the SharePoint tools from `server.py`** to avoid duplication — let the remote server handle all SharePoint operations.
- **Keep `server.py` lean** — only include custom tools that add value beyond what Microsoft provides.
- Distribute the `mcp.json` configuration via your organization's shared VS Code settings or a dotfiles repo.

### Scaling the Custom Server (If Required)

If you must use the custom server at scale (e.g., you need tools Microsoft doesn't provide), consider these mitigations:

- **Use Azure Key Vault** instead of `.env` files for secret distribution.
- **Use managed identity** if developers run VS Code in a cloud-hosted environment (e.g., GitHub Codespaces, Azure Dev Box).
- **Move the custom server to a remote deployment** (host it as a web service) so developers connect via HTTP instead of running it locally — similar architecture to the Microsoft remote server but under your control.
- **Implement per-user auth** in your custom server using OAuth2 device code flow or PKCE instead of a shared client secret.

---

## Summary

| Scale Factor | Custom Local | Microsoft Remote | Winner at Scale |
|---|---|---|---|
| Onboarding 100+ devs | Complex (Python + secrets) | Simple (JSON + sign-in) | **Remote** |
| Security posture | Shared secret risk | Per-user Entra auth | **Remote** |
| Compliance / audit | Weak (shared identity) | Strong (per-user) | **Remote** |
| Maintenance burden | High (your code) | None (Microsoft's code) | **Remote** |
| Customization | Unlimited | Limited | **Custom** |
| Non-SharePoint tools | Supported | Not supported | **Custom** |

**Bottom line:** Use the Microsoft remote server for SharePoint access at enterprise scale. Supplement with a lean custom server only for capabilities the remote server doesn't cover.
