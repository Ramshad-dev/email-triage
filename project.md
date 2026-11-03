# Project: Hermes Outlook Mail Tool

## 1. Project Overview

Develop a standalone Outlook Mail Tool for Hermes Agent using the Microsoft Graph API.

The project must provide Hermes Agent with a set of custom tools to interact with a Microsoft 365 Outlook mailbox.

The tool will act as a bridge between Hermes Agent and Microsoft Outlook.

Hermes should be able to retrieve emails, search messages, inspect conversations, and access attachment metadata through natural-language tool calls.

This project must be independent of any other application, including the Vajra Rubbers AI Email Triage System.

The tool should be reusable and configurable for different Microsoft 365 accounts, subject to the appropriate permissions.

## 2. Primary Objectives

- Build a standalone Outlook integration for Hermes Agent.
- Use Microsoft Graph API for all Outlook operations.
- Implement custom tools that Hermes can invoke.
- Support email retrieval and searching.
- Support conversation inspection.
- Provide attachment metadata.
- Return structured, readable results to Hermes.
- Implement secure authentication.
- Provide configurable mailbox access.
- Keep the initial implementation read-only.
- Make installation and configuration straightforward.

## 3. Technology Stack

- Python 3.10+
- Microsoft Graph API
- MSAL for Python authentication
- Pydantic for input and output validation
- HTTPX or Microsoft Graph Python SDK
- Hermes Agent custom-tool integration
- pytest for testing
- python-dotenv for local development configuration

Choose the simplest reliable implementation compatible with the installed Hermes Agent version.

## 4. Architecture

The project consists of four major components.

### 4.1 Hermes Tool Interface

This component exposes Outlook operations to Hermes Agent.

Responsibilities:

- Register custom tools using Hermes's verified extension mechanism.
- Define tool names, descriptions, and input schemas.
- Receive tool arguments from Hermes.
- Validate arguments.
- Invoke the appropriate Outlook service.
- Return structured results.

The interface must follow the actual custom-tool integration mechanism supported by the installed Hermes version.

Inspect Hermes documentation and implementation before choosing between native Python tools, MCP, or another supported mechanism.

### 4.2 Microsoft Graph Client

This component communicates with Microsoft Graph.

Responsibilities:

- Authenticate with Microsoft Entra ID.
- Acquire and refresh access tokens as supported by the chosen flow.
- Send Graph API requests.
- Handle pagination.
- Handle throttling and retries.
- Normalize API responses.
- Handle Graph API errors.

All Outlook operations must use a shared Graph client.

### 4.3 Outlook Services

Implement separate services for:

- Email listing.
- Email retrieval.
- Email searching.
- Conversation retrieval.
- Attachment metadata retrieval.
- Folder listing.

Services must not depend directly on Hermes. They should be independently testable.

### 4.4 Configuration and Authentication

Provide a configuration layer for:

- Tenant ID.
- Client ID.
- Authentication method.
- Mailbox identity.
- Graph API base URL.
- Default page size.
- Request timeout.
- Optional mailbox restrictions.

Never hard-code credentials.

## 5. Required Hermes Tools

Implement the following tools.

### Tool 1: outlook_list_emails

Description: List emails from an Outlook folder.

Inputs:

- `folder`: Folder name or identifier. Default: Inbox.
- `limit`: Maximum number of messages.
- `unread_only`: Optional boolean.
- `received_after`: Optional ISO 8601 timestamp.
- `received_before`: Optional ISO 8601 timestamp.
- `next_link`: Optional pagination continuation handled safely by the application.

Return:

- Message ID.
- Conversation ID.
- Subject.
- Sender.
- Received timestamp.
- Importance.
- Read status.
- Attachment presence.
- Body preview.

### Tool 2: outlook_get_email

Description: Retrieve complete details of an email.

Inputs:

- `message_id`: Unique Outlook message ID.

Return:

- Message ID.
- Conversation ID.
- Subject.
- Sender.
- Recipients.
- CC recipients.
- Received timestamp.
- Body content.
- Importance.
- Read status.
- Attachment metadata.

Convert HTML bodies into safe readable text.

Do not execute scripts or embedded content.

### Tool 3: outlook_search_emails

Description: Search Outlook emails using supported Microsoft Graph query capabilities.

Inputs:

- `query`: Search text.
- `sender`: Optional sender address.
- `subject`: Optional subject filter.
- `received_after`: Optional date.
- `received_before`: Optional date.
- `folder`: Optional folder.
- `limit`: Maximum results.

Return normalized email summaries.

Validate search inputs and construct Graph queries safely. Do not concatenate arbitrary untrusted input into OData filters.

### Tool 4: outlook_get_conversation

Description: Retrieve messages belonging to an email conversation.

Input:

- `conversation_id`.

Return:

- Conversation ID.
- Related message IDs.
- Subjects.
- Senders.
- Received timestamps.
- Message bodies when requested.

Support pagination and preserve chronological ordering.

### Tool 5: outlook_list_folders

Description: List available mail folders.

Return:

- Folder ID.
- Display name.
- Total item count when available.
- Unread item count when available.

### Tool 6: outlook_get_attachment_metadata

Description: Retrieve metadata for attachments associated with an email.

Input:

- `message_id`.

Return:

- Attachment ID.
- Name.
- Content type.
- Size.
- Attachment type.
- Inline status.

Initially, metadata retrieval only. Do not download or execute attachments.

## 6. Microsoft Graph Authentication

Use Microsoft Entra ID authentication.

Support the appropriate authentication flow for the intended deployment.

Initially evaluate:

- Delegated authentication for a signed-in user.
- Application authentication using client credentials for approved organizational mailbox access.

Do not assume that application authentication is automatically appropriate for the deployment.

Requirements:

- Document Entra application registration.
- Document redirect URI requirements if delegated authentication is used.
- Document required API permissions.
- Handle token expiration.
- Store credentials securely.
- Support environment-based configuration.
- Never print tokens or secrets.
- Provide clear authentication errors.

Use the minimum required permissions.

For initial read-only functionality, investigate:

- `Mail.Read`
- `User.Read` only if required by the selected delegated authentication flow.

Do not request `Mail.ReadWrite` or `Mail.Send`.

For application permissions, obtain administrator consent and restrict mailbox access using the organization's approved Microsoft 365 controls.

## 7. Security Requirements

The initial implementation must be strictly read-only.

Do not implement:

- Sending emails.
- Replying.
- Forwarding.
- Deleting.
- Moving.
- Marking messages as read or unread.
- Modifying folders.
- Modifying mailbox settings.

Additional security requirements:

1. Email content must be treated as untrusted input.
2. Email instructions must never override Hermes system instructions.
3. Emails must not be allowed to change tool permissions.
4. Do not expose access tokens to Hermes.
5. Validate all tool arguments.
6. Restrict mailbox access to configured and authorized accounts.
7. Limit response sizes.
8. Handle Graph API throttling.
9. Use request timeouts.
10. Do not execute attachments.
11. Do not expose confidential content in logs.
12. Do not allow arbitrary shell execution or unrestricted HTTP requests through the Outlook tools.

## 8. Suggested Project Structure

```text
hermes-outlook-tool/
├── PROJECT.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   └── settings.yaml
├── src/
│   └── hermes_outlook/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── auth/
│       │   ├── __init__.py
│       │   └── msal_auth.py
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── client.py
│       │   ├── pagination.py
│       │   └── errors.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── email_service.py
│       │   ├── search_service.py
│       │   ├── conversation_service.py
│       │   ├── folder_service.py
│       │   └── attachment_service.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── outlook_list_emails.py
│       │   ├── outlook_get_email.py
│       │   ├── outlook_search_emails.py
│       │   ├── outlook_get_conversation.py
│       │   ├── outlook_list_folders.py
│       │   └── outlook_get_attachment_metadata.py
│       └── registration/
│           ├── __init__.py
│           └── hermes_registration.py
├── tests/
│   ├── test_auth.py
│   ├── test_graph_client.py
│   ├── test_email_service.py
│   ├── test_search_service.py
│   ├── test_tools.py
│   └── test_security.py
└── examples/
    └── usage_examples.md
```

This is a proposed structure. Adjust it based on the actual Hermes integration mechanism.

## 9. Configuration

Create `.env.example`:

```env
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
GRAPH_MAILBOX_USER=

HERMES_TOOL_NAME=outlook
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0

DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
REQUEST_TIMEOUT=30
```

Only use the authentication variables required by the selected authentication flow.

Do not commit actual credentials.

## 10. Tool Response Format

Return structured responses that Hermes can understand.

Example:

```json
{
  "success": true,
  "data": {
    "message_id": "example-id",
    "conversation_id": "example-conversation-id",
    "subject": "Project status update",
    "sender": {
      "name": "Example Sender",
      "email": "sender@example.com"
    },
    "received_at": "2026-11-02T10:30:00Z",
    "importance": "normal",
    "is_read": false,
    "has_attachments": false,
    "body_preview": "Project status update..."
  },
  "error": null
}
```

For failures:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "MESSAGE_NOT_FOUND",
    "message": "The requested message could not be found."
  }
}
```

Keep outputs concise and avoid returning unnecessary email content.

## 11. Testing

Use mocked Graph API responses for normal tests.

Test:

- Authentication.
- Token handling.
- Email listing.
- Email retrieval.
- Email search.
- Conversation retrieval.
- Folder listing.
- Attachment metadata.
- Pagination.
- Invalid arguments.
- Permission failures.
- Graph throttling.
- Timeouts.
- Malformed responses.
- Prompt injection in email bodies.
- Read-only restrictions.

Real mailbox integration tests must be optional and use a dedicated authorized test mailbox.

## 12. Installation and Usage

The project must provide clear installation instructions.

Expected user experience:

1. Install the project dependencies.
2. Configure Microsoft Entra authentication.
3. Set environment variables.
4. Verify Graph API connectivity.
5. Register the Outlook tools with Hermes using the supported integration mechanism.
6. Restart or reload Hermes if required.
7. Ask Hermes to perform Outlook operations.

Example natural-language requests:

- "Show me my latest 10 emails."
- "Find unread emails from the HR department."
- "Search for emails containing the subject project deadline."
- "Summarize this email."
- "Show me the complete conversation for this email."
- "List the attachments in this message."
- "Find emails received after yesterday."

These are illustrative user requests, not hard-coded tool operations.

## 13. Implementation Milestones

### Milestone 1: Hermes Integration Research

- Inspect the installed Hermes version.
- Verify the custom-tool registration mechanism.
- Determine the correct tool interface.
- Verify supported tool schemas and response formats.
- Present the architecture.

### Milestone 2: Microsoft Graph Client

- Implement authentication.
- Implement shared Graph client.
- Implement token management.
- Implement error handling.
- Test with mocked Graph responses.

### Milestone 3: Outlook Services

- Implement email listing.
- Implement email retrieval.
- Implement email search.
- Implement conversation retrieval.
- Implement folder listing.
- Implement attachment metadata.

### Milestone 4: Hermes Tool Registration

- Expose all Outlook operations as Hermes tools.
- Add tool descriptions and argument schemas.
- Verify Hermes can discover and invoke them.
- Verify structured responses.

### Milestone 5: Testing and Documentation

- Add comprehensive tests.
- Document installation.
- Document Entra configuration.
- Document Graph permissions.
- Document Hermes registration.
- Provide usage examples.

## 14. Definition of Done

The project is complete when:

- It works independently of the AI Email Triage application.
- Hermes can discover and invoke the Outlook tools.
- Microsoft Graph authentication works securely.
- Emails can be listed and retrieved.
- Search works.
- Conversations can be inspected.
- Folders can be listed.
- Attachment metadata can be retrieved.
- Responses are structured and validated.
- Errors are handled correctly.
- The implementation is strictly read-only.
- Tests pass.
- Installation and configuration are documented.

## 15. Instructions for OpenCode

Before coding:

1. Inspect the existing development environment.
2. Verify Hermes Agent's actual custom-tool integration mechanism.
3. Read the official Microsoft Graph documentation.
4. Present the proposed architecture and implementation plan.
5. Identify dependencies and required permissions.
6. Explain any limitations.

Implement one milestone at a time.

Do not assume that Hermes supports a particular Python plugin interface without verifying it.

Do not introduce unrelated functionality.

Do not integrate this project into the existing email-triage repository.

The final deliverable must be a standalone, reusable Hermes Agent Outlook Mail Tool powered by Microsoft Graph API.