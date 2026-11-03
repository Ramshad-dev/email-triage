#!/usr/bin/env python3
"""Read-only Outlook triage retrieval through ClawLink.

This script only calls read actions. It does not create drafts, move messages,
change categories, send, or delete. Classification and drafting stay with the
Hermes skill.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from clawlink_mcp import ClawLinkMCP, McpError, default_config_path, read_api_key
except ImportError:  # Allow running from the repository root.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from clawlink_mcp import ClawLinkMCP, McpError, default_config_path, read_api_key

MESSAGE_SELECT = [
    "id",
    "subject",
    "from",
    "toRecipients",
    "ccRecipients",
    "receivedDateTime",
    "isRead",
    "categories",
    "conversationId",
    "hasAttachments",
    "importance",
    "bodyPreview",
    "flag",
    "webLink",
]

FOLDER_SELECT = [
    "id",
    "displayName",
    "parentFolderId",
    "totalItemCount",
    "unreadItemCount",
    "childFolderCount",
]

PERSONAL_DOMAINS = {
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "outlook.jp",
    "outlook.de",
}


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_messages(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in ("messages", "value", "items", "data", "output"):
            value = result.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                found = extract_messages(value)
                if found:
                    return found
        for key in ("result", "response"):
            value = result.get(key)
            if isinstance(value, (dict, list)):
                found = extract_messages(value)
                if found:
                    return found
    return []


def mailbox_type(profile: Any) -> str:
    if not isinstance(profile, dict):
        return "unknown"
    email = str(
        profile.get("mail")
        or profile.get("userPrincipalName")
        or profile.get("email")
        or ""
    ).lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain in PERSONAL_DOMAINS:
        return "personal"
    if domain:
        return "work/school"
    return "unknown"


def action_result(
    client: ClawLinkMCP,
    action: str,
    payload: dict[str, Any],
    errors: list[dict[str, str]],
) -> Any:
    try:
        result = client.execute(action, {"user_id": "me", **payload})
    except McpError as exc:
        errors.append({"action": action, "error": str(exc)})
        return None
    if isinstance(result, dict) and "output" in result:
        return result["output"]
    return result


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    config = Path(args.config).expanduser() if args.config else default_config_path()
    client = ClawLinkMCP(
        read_api_key(config), url=args.url, timeout=args.timeout
    )

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=args.days)
    sent_since = now - timedelta(days=args.sent_days) if args.sent_days else None
    errors: list[dict[str, str]] = []

    profile = action_result(
        client,
        "get_profile",
        {"select": ["id", "displayName", "mail", "userPrincipalName"]},
        errors,
    )
    folders_result = action_result(
        client,
        "list_mail_folders",
        {"top": args.folder_top, "select": FOLDER_SELECT},
        errors,
    )
    folders = extract_messages(folders_result)

    inbox_payload: dict[str, Any] = {
        "folder": args.folder,
        "top": args.top,
        "orderby": "receivedDateTime desc",
        "received_date_time_ge": iso_utc(since),
        "select": MESSAGE_SELECT,
    }
    inbox = action_result(client, "list_messages", inbox_payload, errors)

    sent = None
    if not args.no_sent:
        sent_payload: dict[str, Any] = {
            "folder": "sentitems",
            "top": args.sent,
            "orderby": "sentDateTime desc",
            "select": [
                "id",
                "subject",
                "toRecipients",
                "sentDateTime",
                "bodyPreview",
            ],
        }
        if sent_since is not None:
            sent_payload["received_date_time_ge"] = iso_utc(sent_since)
        sent = action_result(client, "list_messages", sent_payload, errors)

    inbox_messages = extract_messages(inbox)
    sent_messages = extract_messages(sent) if sent is not None else []

    return {
        "generated_at": iso_utc(now),
        "scope": {
            "account": "me",
            "folder": args.folder,
            "days": args.days,
            "since": iso_utc(since),
            "top": args.top,
            "sent_days": args.sent_days,
            "sent_sample": args.sent,
            "mutations": "none",
        },
        "mailbox_type": mailbox_type(profile),
        "profile": profile,
        "folders": folders,
        "inbox": {
            "returned": len(inbox_messages),
            "unread": sum(1 for item in inbox_messages if item.get("isRead") is False),
            "messages": inbox_messages,
            "raw": inbox,
        },
        "sent": {
            "returned": len(sent_messages),
            "messages": sent_messages,
            "raw": sent,
        },
        "errors": errors,
    }


def print_summary(report: dict[str, Any]) -> None:
    scope = report["scope"]
    profile = report.get("profile") or {}
    account = ""
    if isinstance(profile, dict):
        account = profile.get("mail") or profile.get("userPrincipalName") or ""
    print(f"Generated: {report['generated_at']}")
    print(f"Account:   {account or 'unknown'}")
    print(f"Mailbox:   {report.get('mailbox_type')}")
    print(
        f"Inbox:     {report['inbox']['returned']} messages "
        f"({report['inbox']['unread']} unread) "
        f"since {scope['since']} · cap {scope['top']}"
    )
    print(f"Sent:      {report['sent']['returned']} sampled")
    if report["errors"]:
        print(f"Errors:    {len(report['errors'])}")
        for error in report["errors"]:
            print(f"  - {error['action']}: {error['error']}")
    for message in report["inbox"]["messages"]:
        sender = ""
        sender_info = message.get("from") or {}
        if isinstance(sender_info, dict):
            email_info = sender_info.get("emailAddress") or {}
            if isinstance(email_info, dict):
                sender = email_info.get("address") or email_info.get("name") or ""
        categories = ", ".join(message.get("categories") or [])
        print(
            f"  [{'read' if message.get('isRead') else 'unread'}] "
            f"{message.get('receivedDateTime', '')} | {sender} | "
            f"{message.get('subject', '(no subject)')}"
            f"{' | ' + categories if categories else ''}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retrieve read-only Outlook triage data through ClawLink."
    )
    parser.add_argument("--config", help="Path to Hermes config.yaml")
    parser.add_argument("--url", default="https://claw-link.dev/api/mcp")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--folder", default="inbox")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--folder-top", type=int, default=50)
    parser.add_argument("--sent", type=int, default=15)
    parser.add_argument("--sent-days", type=int, default=90)
    parser.add_argument("--no-sent", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report")
    parser.add_argument("--output", type=Path, help="Write the full JSON report to a file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_report(args)
    except (McpError, SystemExit) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Wrote {args.output}")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_summary(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
