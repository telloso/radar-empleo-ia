"""Import and export the n8n workflows kept in n8n/workflows/.

The JSON files in the repo are clean templates: no Telegram chat id, no
credential ids and no owner data. `import` fills those in (chat id from .env,
credential ids from the running n8n, matched by credential name); `export`
pulls the workflows back out of n8n and strips them again, ready to commit.

After an import, publish the scheduled workflows from the n8n editor (the
script reminds you which ones).

Usage, from the repo root with `docker compose up -d` running:
    python3 n8n/workflows.py import
    python3 n8n/workflows.py export
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "n8n" / "workflows"
ENV_FILE = REPO_ROOT / ".env"
CHAT_ID_PLACEHOLDER = "YOUR_TELEGRAM_CHAT_ID"
# Scratch file inside the n8n container, used to pass JSON in and out.
CONTAINER_FILE = "/tmp/radar-workflows.json"
# Fields n8n adds on export that only make sense in one instance (owner,
# version counters, timestamps...). They stay out of the repo.
INSTANCE_KEYS = {
    "createdAt", "updatedAt", "versionId", "activeVersionId", "versionCounter",
    "triggerCount", "shared", "meta", "pinData", "staticData", "isArchived",
    "versionMetadata", "sourceWorkflowId", "nodeGroups",
}


def read_env(name: str) -> str:
    for line in ENV_FILE.read_text().splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name and value.strip():
            return value.strip()
    sys.exit(f"{name} is missing in .env")


def in_n8n(*command: str, stdin: str | None = None) -> str:
    """Run a command inside the n8n container and return its output."""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "n8n", *command],
        cwd=REPO_ROOT, input=stdin, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"Command failed: {' '.join(command)}\n{result.stderr}")
    return result.stdout


def credential_ids() -> dict[str, str]:
    """Map each n8n credential name to its id. Secrets stay encrypted."""
    in_n8n("n8n", "export:credentials", "--all", f"--output={CONTAINER_FILE}")
    credentials = json.loads(in_n8n("cat", CONTAINER_FILE))
    in_n8n("rm", CONTAINER_FILE)
    return {cred["name"]: cred["id"] for cred in credentials}


def repo_workflows() -> dict[str, Path]:
    """Map each workflow id in the repo to its file."""
    return {
        json.loads(path.read_text())["id"]: path
        for path in sorted(WORKFLOWS_DIR.glob("*.json"))
    }


def import_workflows() -> None:
    chat_id = read_env("TELEGRAM_CHAT_ID")
    credentials = credential_ids()

    workflows = []
    for path in repo_workflows().values():
        workflow = json.loads(path.read_text().replace(CHAT_ID_PLACEHOLDER, chat_id))
        for node in workflow["nodes"]:
            for credential in node.get("credentials", {}).values():
                if credential["name"] not in credentials:
                    sys.exit(f"Create the n8n credential \"{credential['name']}\" first")
                credential["id"] = credentials[credential["name"]]
        workflows.append(workflow)

    in_n8n("sh", "-c", f"cat > {CONTAINER_FILE}", stdin=json.dumps(workflows))
    in_n8n("n8n", "import:workflow", f"--input={CONTAINER_FILE}")
    in_n8n("rm", CONTAINER_FILE)
    print(f"Imported {len(workflows)} workflows: {', '.join(w['name'] for w in workflows)}")
    # Importing unpublishes workflows, and publishing from the CLI marks them as
    # published without registering their triggers. Publish them from the editor.
    for workflow in workflows:
        if workflow.get("active"):
            print(f"Publish \"{workflow['name']}\" from the n8n editor, or its trigger will not run")


def export_workflows() -> None:
    chat_id = read_env("TELEGRAM_CHAT_ID")
    tracked = repo_workflows()

    in_n8n("n8n", "export:workflow", "--all", f"--output={CONTAINER_FILE}")
    exported = json.loads(in_n8n("cat", CONTAINER_FILE))
    in_n8n("rm", CONTAINER_FILE)

    # Only workflows that already live in the repo: experiments stay in n8n.
    for workflow in (w for w in exported if w["id"] in tracked):
        clean = {key: value for key, value in workflow.items() if key not in INSTANCE_KEYS}
        for node in clean["nodes"]:
            for credential in node.get("credentials", {}).values():
                credential.pop("id", None)
        text = json.dumps(clean, indent=2, ensure_ascii=False).replace(chat_id, CHAT_ID_PLACEHOLDER)
        tracked[workflow["id"]].write_text(text + "\n")
        print(f"Exported {workflow['name']} -> {tracked[workflow['id']].relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    commands = {"import": import_workflows, "export": export_workflows}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
