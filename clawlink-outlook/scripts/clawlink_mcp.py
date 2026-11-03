#!/usr/bin/env python3
"""Minimal ClawLink MCP client using only the Python standard library.

Reads the ClawLink API key from the Hermes config by default. The key is never
printed. Supports the meta-tools used by the Outlook triage workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "https://claw-link.dev/api/mcp"
PROTOCOL_VERSION = "2025-03-26"


def default_config_path() -> Path:
    explicit = os.environ.get("HERMES_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    home = os.environ.get("HERMES_HOME")
    if home:
        return Path(home).expanduser() / "config.yaml"
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "hermes" / "config.yaml"
    return Path.home() / ".hermes" / "config.yaml"


def read_api_key(config_path: Path) -> str:
    env_key = os.environ.get("CLAWLINK_API_KEY")
    if env_key:
        return env_key.strip()
    if not config_path.exists():
        raise SystemExit(f"Hermes config not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    match = re.search(r"x-clawlink-api-key:\s*(\S+)", text)
    if not match:
        raise SystemExit(f"No x-clawlink-api-key entry in {config_path}")
    return match.group(1).strip().strip("\"'")


class McpError(RuntimeError):
    pass


class ClawLinkMCP:
    def __init__(self, api_key: str, url: str = DEFAULT_URL, timeout: float = 90.0):
        self.api_key = api_key
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._request_id = 0
        self._initialized = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "x-clawlink-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _post(self, payload: dict[str, Any], *, notify: bool = False) -> Any:
        if not notify:
            self._request_id += 1
            payload["id"] = self._request_id
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=data, headers=self._headers(), method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                session = response.headers.get("Mcp-Session-Id") or response.headers.get(
                    "mcp-session-id"
                )
                if session:
                    self.session_id = session
                raw = response.read().decode("utf-8", "replace")
                return self._decode(raw, response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:2000]
            raise McpError(f"HTTP {exc.code}: {body}") from None
        except urllib.error.URLError as exc:
            raise McpError(f"Network error: {exc.reason}") from None

    @staticmethod
    def _decode(raw: str, content_type: str) -> Any:
        if not raw.strip():
            return None
        if "text/event-stream" in content_type or raw.lstrip().startswith(
            ("event:", "data:")
        ):
            events: list[str] = []
            for block in raw.replace("\r\n", "\n").split("\n\n"):
                data: list[str] = []
                for line in block.splitlines():
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                if data:
                    events.append("\n".join(data))
            for event in reversed(events):
                try:
                    return json.loads(event)
                except json.JSONDecodeError:
                    continue
            raise McpError(f"Could not parse SSE response: {raw[:500]}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise McpError(f"Non-JSON response: {raw[:500]}") from None

    def initialize(self) -> None:
        if self._initialized:
            return
        response = self._post(
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "email-triage", "version": "0.1.0"},
                },
            }
        )
        if response is None:
            raise McpError("Empty initialize response")
        if "error" in response:
            raise McpError(f"Initialize failed: {response['error']}")
        self._post(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            notify=True,
        )
        self._initialized = True

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self._initialized:
            self.initialize()
        response = self._post(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        if response is None:
            raise McpError(f"Empty response from {name}")
        if "error" in response:
            raise McpError(f"{name} failed: {response['error']}")
        result = response.get("result") or {}
        if result.get("isError"):
            texts = [
                item.get("text", "")
                for item in result.get("content", [])
                if item.get("type") == "text"
            ]
            raise McpError(f"{name} returned an error: {' '.join(texts)[:1000]}")
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        texts = [
            item.get("text", "")
            for item in result.get("content", [])
            if item.get("type") == "text"
        ]
        if not texts:
            return result
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except json.JSONDecodeError:
                return texts[0]
        return texts

    def execute(
        self,
        action_id: str,
        action_input: dict[str, Any],
        *,
        integration_id: str = "outlook",
        confirm: bool | None = None,
        connection_id: str | int | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        arguments: dict[str, Any] = {
            "integration_id": integration_id,
            "action_id": action_id,
            "input": action_input,
        }
        if confirm is not None:
            arguments["confirm"] = confirm
        if connection_id is not None:
            arguments["connection_id"] = connection_id
        if idempotency_key is not None:
            arguments["idempotency_key"] = idempotency_key
        return self.call("clawlink_execute", arguments)


def _print(value: Any) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def _load_input(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    if value == "-":
        value = sys.stdin.read()
    elif value.startswith("@"):
        value = Path(value[1:]).read_text(encoding="utf-8")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise SystemExit("--input must decode to a JSON object")
    return parsed


def _client(args: argparse.Namespace) -> ClawLinkMCP:
    config = Path(args.config).expanduser() if args.config else default_config_path()
    return ClawLinkMCP(
        read_api_key(config),
        url=args.url or DEFAULT_URL,
        timeout=args.timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call ClawLink MCP meta-tools from the command line."
    )
    parser.add_argument("--config", help="Path to Hermes config.yaml")
    parser.add_argument("--url", default=DEFAULT_URL, help="ClawLink MCP URL")
    parser.add_argument("--timeout", type=float, default=90.0)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="Show the ClawLink account")

    connection = sub.add_parser("connection", help="Show one integration connection")
    connection.add_argument("--integration", default="outlook")

    actions = sub.add_parser("actions", help="List actions for an integration")
    actions.add_argument("--integration", default="outlook")
    actions.add_argument("--page", type=int, default=None)
    actions.add_argument("--intent", default=None)
    actions.add_argument("--compact", action="store_true")

    action = sub.add_parser("action", help="Show one action schema")
    action.add_argument("--integration", default="outlook")
    action.add_argument("--action", required=True)

    execute = sub.add_parser("execute", help="Execute one action")
    execute.add_argument("--integration", default="outlook")
    execute.add_argument("--action", required=True)
    execute.add_argument("--input", default=None, help="JSON object, @file, or - for stdin")
    execute.add_argument("--connection-id", default=None)
    execute.add_argument("--idempotency-key", default=None)
    execute.add_argument(
        "--confirm",
        action="store_true",
        help="Set confirm=true at the ClawLink execute level for write actions",
    )

    raw = sub.add_parser("raw", help="Call any MCP tool by name")
    raw.add_argument("--tool", required=True)
    raw.add_argument("--arguments", default="{}")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = _client(args)
    try:
        if args.command == "whoami":
            _print(client.call("clawlink_whoami", {}))
        elif args.command == "connection":
            _print(
                client.call(
                    "clawlink_get_connection", {"integration_id": args.integration}
                )
            )
        elif args.command == "actions":
            payload: dict[str, Any] = {"integration_id": args.integration}
            if args.page is not None:
                payload["page"] = args.page
            if args.intent:
                payload["intent"] = args.intent
            if args.compact:
                payload["compact"] = True
            _print(client.call("clawlink_list_actions", payload))
        elif args.command == "action":
            _print(
                client.call(
                    "clawlink_get_action",
                    {"integration_id": args.integration, "action_id": args.action},
                )
            )
        elif args.command == "execute":
            _print(
                client.execute(
                    args.action,
                    _load_input(args.input),
                    integration_id=args.integration,
                    confirm=True if args.confirm else None,
                    connection_id=args.connection_id,
                    idempotency_key=args.idempotency_key,
                )
            )
        elif args.command == "raw":
            _print(client.call(args.tool, _load_input(args.arguments)))
        else:
            raise SystemExit(f"Unknown command: {args.command}")
    except McpError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
