# SQLite FastMCP Database Server Lab

This project implements a small SQLite-backed MCP server with FastMCP. The server exposes a student learning analytics database through three tools:

- `search`
- `insert`
- `aggregate`

It also exposes schema context as MCP resources so an MCP client can inspect the database before deciding which tools to call.

## Project Structure

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  tests/
    test_db.py
    test_mcp_server.py
requirements.txt
```

## Dataset

The SQLite database contains three related tables:

- `students`: student identity, email, cohort, and creation timestamp
- `courses`: course code, title, and credits
- `enrollments`: student-course links with score, status, and enrollment timestamp

Seed data includes cohorts `A1`, `A2`, and `B1`, multiple courses, and enrollment scores/statuses suitable for search and aggregate demos.

## Setup

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Initialize or reset the database:

```powershell
python implementation/init_db.py --reset
```

Start the MCP server over stdio:

```powershell
python implementation/mcp_server.py
```

The default database path is:

```text
implementation/learning_analytics.sqlite3
```

To use a different database path, set `SQLITE_LAB_DB_PATH`.

## MCP Tools

### `search`

Search rows with safe filters, selected columns, ordering, limit, and offset.

Example arguments:

```json
{
  "table": "students",
  "filters": {"column": "cohort", "op": "eq", "value": "A1"},
  "columns": ["id", "name", "cohort"],
  "limit": 3,
  "order_by": "name"
}
```

Supported filter operators:

- `eq`
- `ne`
- `gt`
- `gte`
- `lt`
- `lte`
- `like`
- `in`

### `insert`

Insert one row and return the inserted payload.

Example arguments:

```json
{
  "table": "students",
  "values": {
    "name": "Minh Demo",
    "email": "minh.demo@example.com",
    "cohort": "A1"
  }
}
```

### `aggregate`

Run a safe aggregate query.

Example arguments:

```json
{
  "table": "enrollments",
  "metric": "avg",
  "column": "score",
  "group_by": "status"
}
```

Supported metrics:

- `count`
- `avg`
- `sum`
- `min`
- `max`

## MCP Resources

Full database schema:

```text
schema://database
```

Single table schema:

```text
schema://table/students
schema://table/courses
schema://table/enrollments
```

Schema resources return JSON text with table names, column names, SQLite types, primary keys, nullability, defaults, and foreign keys.

## Safety Behavior

The server rejects unsafe or invalid requests before executing SQL:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate metrics
- aggregate metrics on non-numeric columns
- empty inserts
- invalid identifiers such as SQL injection-style table or column names
- invalid pagination values

SQL values use parameterized placeholders. User-provided table and column names are validated against the live SQLite schema before being quoted into SQL.

## Verification

Run automated tests:

```powershell
python -m pytest implementation/tests
```

Run the repeatable MCP smoke test:

```powershell
python implementation/verify_server.py
```

The smoke test verifies:

- tools are discoverable
- schema resources are discoverable
- `schema://database` is readable
- valid `search` call succeeds
- valid `aggregate` call succeeds
- valid `insert` call succeeds
- invalid table access returns a clear error

## Inspector

You can inspect tools and resources with MCP Inspector:

```powershell
npx -y @modelcontextprotocol/inspector C:\Users\fansa\miniconda3\python.exe D:\AI_in_Action\Track3\Day26-Track3-2A202600251\implementation\mcp_server.py
```

In Inspector, verify:

- tools show `search`, `insert`, and `aggregate`
- resources show `schema://database`
- resource templates show `schema://table/{table_name}`
- valid calls return structured JSON
- invalid calls return clear errors

## Using Codex as MCP Client

For this lab, Codex is the MCP client. The FastMCP Python application remains the MCP server.

Do not use `codex mcp-server` for this submission. That command starts Codex itself as an MCP server, while this lab requires a custom FastMCP server with SQLite tools and schema resources.

Add this server to Codex:

```powershell
codex mcp add sqlite_lab -- C:\Users\fansa\miniconda3\python.exe D:\AI_in_Action\Track3\Day26-Track3-2A202600251\implementation\mcp_server.py
```

Check that Codex registered the server:

```powershell
codex mcp list
codex mcp get sqlite_lab
```

Use absolute paths on Windows to avoid `spawn ... ENOENT` errors.

Suggested Codex demo prompt:

```powershell
codex "Use the sqlite_lab MCP server. Read schema://database, then search top 3 students in cohort A1, then compute average enrollment score by status."
```

Suggested invalid-request prompt:

```powershell
codex "Use the sqlite_lab MCP server and try to search the table missing_table. Show me the error message."
```

For grading/demo, show that Codex can:

- discover or use `search`, `insert`, and `aggregate`
- read `schema://database`
- run a valid `search`
- run a valid `aggregate`
- receive a clear error for an unknown table

## Optional Gemini CLI Backup

Codex is the primary client for this submission. If another client is needed, Gemini CLI can also be configured:

```powershell
gemini mcp add sqlite-lab C:\Users\fansa\miniconda3\python.exe D:\AI_in_Action\Track3\Day26-Track3-2A202600251\implementation\mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

## Two-Minute Demo Script

1. Run `python implementation/init_db.py --reset`.
2. Run `python implementation/verify_server.py`.
3. Open Inspector and show tools/resources.
4. Run a valid `search` for cohort `A1`.
5. Run `aggregate` average score by `status`.
6. Insert a new student.
7. Run an invalid table request and show the clear error.
8. Run the Codex prompt to show a real MCP client using the server.
