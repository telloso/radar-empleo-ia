# Daily digest with n8n

Every day at 08:30 an n8n workflow sends the best jobs scored in the last 24 hours to Telegram:

```
Schedule (08:30) → Postgres: top 5 jobs scored in the last 24 h → IF any? ─yes→ Code: one HTML message → Telegram
                                                                            └no─→ Telegram: "no new jobs"
```

- **Query**: a CTE with `DISTINCT ON` takes each job's latest score, and `count(*) OVER ()` gives the total before `LIMIT 5` ("top 5 of 12"). It filters by scoring date, not first-seen date, so a job delayed by the daily limit still reaches a digest.
- **Always a message**: the Postgres node outputs one empty item when there are no rows, so the IF can send "no new jobs". Silence would look the same as a broken workflow.
- **Escaped HTML**: job titles are third-party text, so `&`, `<` and `>` are escaped before Telegram parses the message.
- **Errors**: a second workflow (Error Trigger → Telegram) is set as the digest's error workflow, so any failure (database down, revoked token) sends an alert with the failing node.
- **Least privilege**: n8n reads the jobs as `n8n_reader` (`db/init/06-create-n8n-reader.sh`), a role that can only `SELECT` from `jobs` and `scores`.
- **Secrets**: the bot token is an n8n credential, encrypted with `N8N_ENCRYPTION_KEY`; workflows only reference it by name. Node access to environment variables stays blocked (n8n's secure default).

Workflows are kept in Git as clean templates (`n8n/workflows/*.json`): no Telegram chat id, no credential ids, no owner data. `n8n/workflows.py` moves them in and out of the running n8n:

```bash
python3 n8n/workflows.py import   # fills in TELEGRAM_CHAT_ID from .env and credential ids by name
python3 n8n/workflows.py export   # pulls them back and strips personal and instance data
```

Setup on a new instance: create the credentials `Telegram Radar` (bot token from @BotFather) and `Postgres Radar (read-only)` (host `db`, user `n8n_reader`), run `import`, then publish the digest **from the n8n editor**. Importing unpublishes workflows, and publishing from the CLI marks them as published without registering their triggers: the schedule silently never ran until it was published from the editor.

## Claude Code over MCP

n8n has a built-in MCP server (`/mcp-server/http`), and Claude Code is connected to it as an MCP client:

```bash
claude mcp add --transport http n8n http://localhost:5678/mcp-server/http --header "Authorization: Bearer <token>"
```

Claude Code can then search the workflows, inspect executions ("did today's digest run?") or run the digest, without opening the editor. The connection is stored in the user's local Claude Code config, not in the repo, and only the daily digest is enabled for MCP access.

Limits worth knowing:

- Bumping `PROMPT_VERSION` rescores old jobs, and they would appear in the next digest as if they were new.
- n8n cannot start the Python containers itself: that would mean giving it the Docker socket, which is control over the whole host.
