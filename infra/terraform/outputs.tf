output "server_ip" {
  description = "Public IPv4 address of the server"
  value       = hcloud_server.radar.ipv4_address
}
