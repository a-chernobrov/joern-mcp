#!/usr/bin/env python3
"""
Joern MCP Server.
Использует эндпоинт /query-sync — синхронно, без опроса состояния.
Запуск: joern --server
Затем добавьте этот сервер в конфиг MCP (например, Trae).
"""

import asyncio
import json
import urllib.request
import urllib.error
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

JOERN_BASE   = "http://localhost:8080"
TIMEOUT      = 120   # секунды — большие проекты требуют времени
MAX_RESULT   = 8000  # символы — ограничение, чтобы не забивать контекст

app = Server("joern-mcp")


def joern_exec(query: str) -> dict:
    """Отправить запрос в /query-sync и вернуть результат синхронно."""
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"{JOERN_BASE}/query-sync",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def format_result(result: dict) -> str:
    stdout = result.get("stdout", "").strip()
    stderr = result.get("stderr", "").strip()

    out = []
    if stdout:
        if len(stdout) > MAX_RESULT:
            out.append(f"[truncated: showing {MAX_RESULT} of {len(stdout)} chars]\n")
            stdout = stdout[:MAX_RESULT] + "\n...(truncated)"
        out.append(stdout)
    if stderr:
        out.append(f"\n[stderr]:\n{stderr[:2000]}")
    if not stdout and not stderr:
        out.append("(no output)")

    return "\n".join(out)


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="joern_query",
            description=(
                "Execute any Joern/CPGQL query. "
                "The CPG must be loaded first via joern_load. "
                "Returns stdout/stderr from Joern interpreter — use errors to fix and retry.\n\n"
                "Examples:\n"
                "  cpg.method.name.l\n"
                "  cpg.call.name(\"exec\").caller.name.l\n"
                "  cpg.identifier.name(\"_GET|_POST\").l\n"
                "  cpg.method.name(\"login\").ast.isCall.name.l\n"
                "  sink.reachableByFlows(source).p"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Any valid Joern/CPGQL Scala expression",
                    }
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="joern_load",
            description=(
                "Load source code and build a CPG. "
                "Supports PHP, Java, JS, Python, C/C++ etc. "
                "Use absolute paths. Large projects may take 1-2 minutes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to source file or directory",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional name for this project in workspace",
                    },
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="joern_workspace",
            description="Show loaded projects and active CPG in Joern workspace.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        loop = asyncio.get_event_loop()

        if name == "joern_query":
            query = arguments["query"]
            result = await loop.run_in_executor(None, joern_exec, query)
            return [types.TextContent(type="text", text=format_result(result))]

        elif name == "joern_load":
            path = arguments["path"]
            proj = arguments.get("project_name", "")
            if proj:
                query = f'importCode("{path}", "{proj}")'
            else:
                query = f'importCode("{path}")'
            result = await loop.run_in_executor(None, joern_exec, query)
            return [types.TextContent(type="text", text=format_result(result))]

        elif name == "joern_workspace":
            result = await loop.run_in_executor(None, joern_exec, "workspace")
            return [types.TextContent(type="text", text=format_result(result))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except urllib.error.URLError as e:
        return [types.TextContent(type="text", text=
            f"[CONNECTION ERROR] Cannot reach Joern at {JOERN_BASE}\n"
            f"Make sure 'joern --server' is running.\nDetails: {e}"
        )]
    except Exception as e:
        return [types.TextContent(type="text", text=f"[ERROR] {type(e).__name__}: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
