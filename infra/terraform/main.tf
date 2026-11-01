terraform {
  required_version = ">= 1.9"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.70"
    }
  }
}

# The API token comes from the HCLOUD_TOKEN environment variable, so it is never
# written to a file.
provider "hcloud" {}

# Only the public half: the private key never leaves this machine.
resource "hcloud_ssh_key" "admin" {
  name       = "radar-admin"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

# Hetzner's firewall drops inbound traffic before it reaches the server, and it
# blocks everything not listed here. Postgres and n8n stay closed: n8n is reached
# through an SSH tunnel. Outbound traffic stays open (job APIs, Claude, Telegram).
resource "hcloud_firewall" "radar" {
  name = "radar-firewall"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["${var.admin_ip}/32"]
  }
}

resource "hcloud_server" "radar" {
  name         = "radar"
  server_type  = var.server_type
  location     = var.location
  image        = "ubuntu-26.04"
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.radar.id]
}
