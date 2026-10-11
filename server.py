#!/usr/bin/env python3
"""
Joern MCP Server.
Использует эндпоинт /query-sync — синхронно, без опроса состояния.
Запуск: joern --server
Затем добавьте этот сервер в конфиг MCP (например, Trae).
"""

import asyncio
import json
import os
import subprocess
import tempfile
import urllib.request
import urllib.error
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

JOERN_BASE   = "http://localhost:8080"
TIMEOUT      = 120   # секунды — большие проекты требуют времени
MAX_RESULT   = 8000  # символы — ограничение, чтобы не забивать контекст
JOERN_PARSE  = os.environ.get("JOERN_PARSE", "joern-parse")

# Явные frontend'ы Joern (--language). Без language importCode угадывает по типу файлов.
LANGUAGES = [
    "JAVASRC", "JAVA", "JAVASCRIPT", "PHP", "PYTHONSRC",
    "CSHARPSRC", "GOLANG", "KOTLIN", "RUBYSRC", "SWIFTSRC", "C",
]

app = Server("joern-mcp")


def build_cpg(path: str, language: str, frontend_args: str = "") -> str:
    """Явно собрать CPG через joern-parse --language. Возвращает путь к cpg.bin."""
    out_dir = tempfile.mkdtemp(prefix="joern_cpg_")
    cpg = os.path.join(out_dir, "cpg.bin")
    cmd = [JOERN_PARSE, path, "--language", language, "-o", cpg]
    if frontend_args:
        cmd += ["--frontend-args", *frontend_args.split()]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    if not os.path.isfile(cpg):
        raise RuntimeError(
            f"joern-parse ({language}) не создал CPG. "
            f"{((proc.stderr or proc.stdout) or '').strip()[:1500]}"
        )
    return cpg


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
                "Load source code and build a CPG. Supports PHP, Java (JAVASRC), "
                "JavaScript/TypeScript (JAVASCRIPT), Python, C/C++, Kotlin, C#, Go, Ruby, Swift. "
                "Use absolute paths. Large projects may take 1-2 minutes. "
                "Pass language to force a frontend (recommended; auto-detection can pick the "
                "wrong frontend on mixed or TS-heavy projects)."
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
                    "language": {
                        "type": "string",
                        "enum": LANGUAGES,
                        "description": "Force a Joern frontend via joern-parse --language "
                        "(JAVASRC for Java, JAVASCRIPT for JS/TS).",
                    },
                    "frontend_args": {
                        "type": "string",
                        "description": "Extra frontend args, e.g. '--no-tsTypes' for JAVASCRIPT.",
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
            language = arguments.get("language")
            frontend_args = arguments.get("frontend_args", "")
            if language:
                try:
                    cpg = await loop.run_in_executor(
                        None, build_cpg, path, language, frontend_args)
                except Exception as e:
                    return [types.TextContent(type="text", text=f"[ERROR] {e}")]
                result = await loop.run_in_executor(None, joern_exec, f'importCpg("{cpg}")')
                return [types.TextContent(type="text", text=
                    format_result(result) + f"\n\n[built with --language {language}]")]
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
