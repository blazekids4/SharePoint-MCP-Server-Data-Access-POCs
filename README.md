# Vantiva MCP Server — SharePoint Data Access POCs

A collection of proof-of-concept implementations demonstrating different ways to give [GitHub Copilot](https://github.com/features/copilot) access to SharePoint content via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

Each POC takes a different approach to data retrieval, allowing teams to evaluate trade-offs around control, security, maintenance, and deployment complexity.

---

## POC Approaches

### 1. [Microsoft Graph API](poc-graph-api/)

A custom Python MCP server that calls the **Microsoft Graph API** directly to access SharePoint sites, pages, files, and document libraries. Hosted on **Azure Container Apps** for centralized deployment.

- **Auth:** App-only client credentials (Azure AD app registration)
- **Transport:** Streamable HTTP (hosted) or stdio (local)
- **Stack:** Python, FastMCP, MSAL, httpx
- **Deployment:** Azure Container Apps via `azd up`

**Best for:** Full control over tool behavior, custom filtering/formatting, combining multiple data sources in one server.

### 2. [Azure AI Search](poc-azure-ai-search/)

An MCP server backed by **Azure AI Search** for indexed, full-text and semantic search over SharePoint content.

- **Auth:** Azure AI Search API keys or managed identity
- **Stack:** TBD

**Best for:** Large-scale content search with relevance ranking, semantic search, and faceted filtering.

### 3. [M365 Copilot Retrieval API](poc-m365-copilot-retrieval-api/)

Uses the **Microsoft 365 Copilot Retrieval API** — a Microsoft-hosted service that provides pre-built access to organizational content without custom server code.

- **Auth:** Delegated user credentials (interactive browser sign-in)
- **Transport:** Streamable HTTP to Microsoft-hosted endpoint
- **Docs:** [M365 Copilot Retrieval API Overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/retrieval/overview)

**Best for:** Zero-code setup, per-user access controls, no infrastructure to manage.

---

## Approach Comparison

| Dimension | Graph API | Azure AI Search | M365 Copilot Retrieval API |
|---|---|---|---|
| **Infrastructure** | Self-hosted (Azure Container Apps) | Self-hosted (Azure AI Search + compute) | Microsoft-hosted |
| **Auth model** | App-only (service principal) | API key / managed identity | Delegated (per-user) |
| **Custom tools** | Yes — full control | Yes — custom index + tools | No — pre-built by Microsoft |
| **Search capability** | Basic Graph search | Full-text + semantic search | Microsoft's relevance engine |
| **Maintenance** | You maintain all code | You maintain index + code | Microsoft maintains |
| **Per-user access control** | No (shared service principal) | Configurable | Yes (native) |

See [documentation/mcp-approaches-comparison.md](documentation/mcp-approaches-comparison.md) for a detailed comparison.

---

## Repository Structure

```
vantiva-mcp-server/
├── poc-graph-api/                    # POC 1: Microsoft Graph API
│   ├── server.py                     #   MCP server implementation
│   ├── Dockerfile                    #   Container build
│   ├── azure.yaml                    #   Azure Developer CLI config
│   ├── requirements.txt              #   Python dependencies
│   ├── README.md                     #   Setup & deployment guide
│   └── infra/                        #   Azure infrastructure (Bicep)
│       ├── main.bicep
│       ├── main.parameters.json
│       └── modules/
├── poc-azure-ai-search/              # POC 2: Azure AI Search
├── poc-m365-copilot-retrieval-api/   # POC 3: M365 Copilot Retrieval API
│   └── README.md
├── documentation/                    # Shared documentation & resources
│   ├── mcp-approaches-comparison.md
│   ├── enterprise-deployment-guide.md
│   ├── hosting-mcp-server-end-to-end.md
│   ├── mcp-hosting-options-azure.md
│   ├── sample-prompts.md
│   └── resources.md
└── .vscode/
    └── mcp.json                      # MCP server configs for all POCs
```

---

## Quick Start

Each POC has its own README with setup instructions. To try the most complete implementation:

```bash
cd poc-graph-api
```

Then follow the [Graph API POC README](poc-graph-api/README.md) for deployment and configuration.

---

## Documentation

| Document | Description |
|---|---|
| [Approach Comparison](documentation/mcp-approaches-comparison.md) | Detailed comparison of all three approaches |
| [Enterprise Deployment Guide](documentation/enterprise-deployment-guide.md) | Scaling MCP servers for enterprise use |
| [Hosting End-to-End](documentation/hosting-mcp-server-end-to-end.md) | Full walkthrough of hosting an MCP server |
| [Azure Hosting Options](documentation/mcp-hosting-options-azure.md) | Azure hosting options for MCP servers |
| [Sample Prompts](documentation/sample-prompts.md) | Example prompts to use with Copilot |
| [Resources](documentation/resources.md) | Links and references |

---

## Prerequisites

- **VS Code** with **GitHub Copilot** and **GitHub Copilot Chat** extensions
- **Azure subscription** (for Graph API and AI Search POCs)
- **Microsoft Entra ID (Azure AD)** tenant
- **Azure Developer CLI (`azd`)** — [Install here](https://aka.ms/azd-install)
