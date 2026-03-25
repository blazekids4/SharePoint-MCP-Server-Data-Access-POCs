"""
SharePoint MCP Server
-------------------
A Model Context Protocol server that exposes tools to GitHub Copilot.
Add your own @mcp.tool() functions below to give Copilot new capabilities.
"""

import os
import json
import httpx
import msal
from mcp.server.fastmcp import FastMCP

# Create the MCP server (name appears in VS Code when discovering tools)
transport = os.environ.get("MCP_TRANSPORT", "stdio")
mcp = FastMCP(
    "sharepoint-mcp",
    host="0.0.0.0" if transport == "streamable-http" else "127.0.0.1",
    port=int(os.environ.get("PORT", "8080")),
)


# ── SharePoint configuration (set via environment variables) ─────────────────
TENANT_ID = os.environ.get("SHAREPOINT_TENANT_ID", "")
CLIENT_ID = os.environ.get("SHAREPOINT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
SHAREPOINT_HOST = os.environ.get("SHAREPOINT_HOST", "yourtenant.sharepoint.com")


def _get_graph_token() -> str:
    """Acquire a Microsoft Graph access token using client credentials."""
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")
    return result["access_token"]


# ── Example tool: greet ──────────────────────────────────────────────────────
@mcp.tool()
def greet(name: str) -> str:
    """Say hello to someone. Use this when the user wants a friendly greeting."""
    return f"Hello, {name}! Welcome to the SharePoint MCP server."


# ── Example tool: add_numbers ────────────────────────────────────────────────
@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together and return the result."""
    return a + b


# ── SharePoint tools ─────────────────────────────────────────────────────────
@mcp.tool()
def get_sharepoint_page(site_name: str, page_name: str) -> str:
    """
    Fetch a SharePoint page's content by site name and page name.

    Args:
        site_name: The SharePoint site name (e.g. "Engineering" or "HR").
        page_name: The page file name including .aspx (e.g. "Home.aspx").
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Resolve the site ID
    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{site_name}"
    with httpx.Client() as client:
        site_resp = client.get(site_url, headers=headers)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        # Get the page from the site pages list
        pages_url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
            f"?$filter=name eq '{page_name}'"
        )
        pages_resp = client.get(pages_url, headers=headers)
        pages_resp.raise_for_status()
        pages = pages_resp.json().get("value", [])

        if not pages:
            return f"No page named '{page_name}' found in site '{site_name}'."

        page_id = pages[0]["id"]

        # Fetch the full page content (web parts)
        content_url = (
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/pages/{page_id}/microsoft.graph.sitePage/canvasLayout"
        )
        content_resp = client.get(content_url, headers=headers)
        content_resp.raise_for_status()

        return json.dumps(content_resp.json(), indent=2)


@mcp.tool()
def list_sharepoint_pages(site_name: str) -> str:
    """
    List all pages in a SharePoint site.

    Args:
        site_name: The SharePoint site name (e.g. "Engineering" or "HR").
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{site_name}"
    with httpx.Client() as client:
        site_resp = client.get(site_url, headers=headers)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        pages_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/pages"
        pages_resp = client.get(pages_url, headers=headers)
        pages_resp.raise_for_status()

        pages = pages_resp.json().get("value", [])
        result = [{"name": p.get("name"), "title": p.get("title"), "id": p.get("id")} for p in pages]
        return json.dumps(result, indent=2)


@mcp.tool()
def search_sharepoint(query: str, site_name: str = "DeveloperCentral") -> str:
    """
    Search for files in a SharePoint site's Documents library matching a query.

    Args:
        query: The search term to find in the Documents library.
        site_name: The SharePoint site name (e.g. "DeveloperCentral").
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{site_name}"
    with httpx.Client() as client:
        site_resp = client.get(site_url, headers=headers)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
        drive_resp = client.get(drive_url, headers=headers)
        drive_resp.raise_for_status()
        drive_id = drive_resp.json()["id"]

        search_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/search(q='{query}')"
        resp = client.get(search_url, headers=headers)
        resp.raise_for_status()

        items = resp.json().get("value", [])
        results = []
        for item in items:
            entry = {
                "name": item.get("name"),
                "webUrl": item.get("webUrl"),
            }
            if "file" in item:
                entry["mimeType"] = item["file"].get("mimeType", "")
                entry["size"] = item.get("size", 0)
            results.append(entry)
        return json.dumps(results, indent=2)


@mcp.tool()
def list_sharepoint_folder(site_name: str, folder_path: str = "") -> str:
    """
    List files and subfolders in a SharePoint document library folder.

    Args:
        site_name: The SharePoint site name (e.g. "DeveloperCentral").
        folder_path: Path inside the default document library (e.g. "API Documentation").
                     Leave empty to list the root of the library.
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{site_name}"
    with httpx.Client() as client:
        site_resp = client.get(site_url, headers=headers)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
        drive_resp = client.get(drive_url, headers=headers)
        drive_resp.raise_for_status()
        drive_id = drive_resp.json()["id"]

        if folder_path:
            items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{folder_path}:/children"
        else:
            items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"

        items_resp = client.get(items_url, headers=headers)
        items_resp.raise_for_status()

        items = items_resp.json().get("value", [])
        result = []
        for item in items:
            entry = {
                "name": item.get("name"),
                "type": "folder" if "folder" in item else "file",
                "id": item.get("id"),
                "webUrl": item.get("webUrl"),
            }
            if "file" in item:
                entry["mimeType"] = item["file"].get("mimeType", "")
                entry["size"] = item.get("size", 0)
            result.append(entry)
        return json.dumps(result, indent=2)


@mcp.tool()
def get_sharepoint_file_content(site_name: str, file_path: str) -> str:
    """
    Read the text content of a file from a SharePoint document library.
    Works with text files (.txt, .md, .json, .csv, .xml, .html) and PDFs.
    For PDFs, extracts all text content using PyMuPDF.

    Args:
        site_name: The SharePoint site name (e.g. "DeveloperCentral").
        file_path: Path to the file inside the default document library
                   (e.g. "API Documentation/REST API Guide.pdf").
    """
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    site_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_HOST}:/sites/{site_name}"
    with httpx.Client() as client:
        site_resp = client.get(site_url, headers=headers)
        site_resp.raise_for_status()
        site_id = site_resp.json()["id"]

        drive_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
        drive_resp = client.get(drive_url, headers=headers)
        drive_resp.raise_for_status()
        drive_id = drive_resp.json()["id"]

        content_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{file_path}:/content"
        content_resp = client.get(content_url, headers=headers, follow_redirects=True)
        content_resp.raise_for_status()
        
        # Check if it's a PDF
        if file_path.lower().endswith('.pdf'):
            import io
            import fitz  # PyMuPDF
            
            # Open PDF from bytes
            pdf_document = fitz.open(stream=content_resp.content, filetype="pdf")
            text = ""
            
            # Extract text from each page
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                text += page.get_text() + "\n"
            
            pdf_document.close()
            return text.strip()
        
        return content_resp.text


if __name__ == "__main__":
    mcp.run(transport=transport)
