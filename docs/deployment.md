# Deployment

The app runs on a Hetzner CX23 (2 vCPU, 4 GB of RAM, about €7.25 a month), created and configured from code in `infra/`:

| Step | Tool | What it does |
| --- | --- | --- |
| Provision | Terraform (`infra/terraform/`) | Creates the server, its SSH key and a firewall |
| Bootstrap | Ansible (`bootstrap.yml`) | First run, as root: creates the `deploy` user |
| Configure | Ansible (`server.yml`) | Security settings, swap and Docker |
| Deploy | Ansible (`deploy.yml`) | Code, secrets, image, services and timers |

```bash
export HCLOUD_TOKEN=...                     # better: read -rs HCLOUD_TOKEN && export HCLOUD_TOKEN
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # then fill in your IP
terraform init && terraform apply

cd ../ansible
printf '[radar]\n%s\n' "$(terraform -chdir=../terraform output -raw server_ip)" > inventory.ini
ansible-playbook bootstrap.yml
ansible-playbook server.yml                 # a second run should report changed=0
ansible-playbook deploy.yml                 # the server pulls from GitHub: push first
```

**Security.** The firewall only allows SSH from one IP, and Postgres and n8n are also bound to `127.0.0.1`, so a mistake in one layer does not expose them. SSH accepts keys only: root and password logins are disabled, and `server.yml` connects as `deploy`, which proves that user works before root is closed. fail2ban and automatic security updates add further layers. n8n is reached through an SSH tunnel:

```bash
ssh -i ~/.ssh/radar_vps -N -L 5678:localhost:5678 deploy@<server-ip>   # then open http://localhost:5678
```

**Secrets.** `.env` and `collector/profile.md` are not in Git: Ansible copies them from the local machine over SSH with mode `600`. Terraform state, variables and the real inventory are git-ignored too, as they hold the server's address and possibly secrets.

**Daily schedule** (Europe/Madrid):

| Time | Run by | What |
| --- | --- | --- |
| 07:30 | systemd timer | Dumps both databases, keeps a week of copies |
| 08:00 | systemd timer | `collector` → `scorer` → `embedder`, stopping at the first failure |
| 08:30 | n8n | Sends the digest to Telegram |

A failed systemd job sends a Telegram alert directly with `curl` (`TELEGRAM_BOT_TOKEN` in `.env`), so it works even if n8n is down. `Persistent=true` runs a missed timer as soon as the server is back.

**Restoring a backup.** Stop n8n first, restore both databases, then start it again. Use the same `N8N_ENCRYPTION_KEY`, or n8n cannot decrypt its credentials. Then publish the digest from the editor if needed.

```bash
docker compose stop n8n
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < radar-YYYY-MM-DD.dump
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d n8n --clean --if-exists' < n8n-YYYY-MM-DD.dump
docker compose up -d n8n
```

Limits worth knowing:

- **Backups live on the same server.** They protect against mistakes and bad runs, not against losing the server. Copying them off the server is the next step.
- **One server, no redundancy**: if it is down, the digest waits. That is fine for a personal tool.
- **A new home IP locks SSH out** until `terraform.tfvars` is updated and `terraform apply` runs, which works because it goes through Hetzner's API.
- **Terraform state is local**, which suits one person. A team would use a remote, encrypted backend with locking.
- **Hetzner has cost alerts but no hard spending cap**, so an alert is set in its console.
