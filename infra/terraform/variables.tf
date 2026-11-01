variable "admin_ip" {
  description = "Public IPv4 address allowed to connect over SSH"
  type        = string
}

variable "ssh_public_key_path" {
  description = "Path to the public SSH key installed on the server"
  type        = string
  default     = "~/.ssh/radar_vps.pub"
}

variable "server_type" {
  description = "Hetzner server type: x86, 2 vCPU, 4 GB of RAM"
  type        = string
  default     = "cx23"
}

variable "location" {
  description = "Hetzner location (fsn1 is Falkenstein, Germany)"
  type        = string
  default     = "fsn1"
}
