# IPs des VMs (host-only)
output "vm_ips" {
  description = "Adresses IP des VMs e-commerce"
  value       = [for vm in virtualbox_vm.ecom_vm : vm.network_adapter[0].ipv4_address]
}

# Ports des services Docker (sur la machine hôte)
output "docker_ports" {
  description = "Ports exposés pour les services Docker"
  value = {
    auth    = var.auth_host_port
    orders  = var.orders_host_port
    gateway = var.gateway_host_port
    front   = var.front_host_port
  }
}

# URL du front accessible sur la machine hôte
output "front_url" {
  description = "URL HTTP du front local"
  value       = "http://127.0.0.1:${var.front_host_port}"
}
