# --- Paramètres VM ---

variable "vm_count" {
  description = "Nombre de VMs VirtualBox à déployer"
  type        = number
  default     = 1
}

variable "vm_host_interface" {
  description = "Nom de l'interface host-only VirtualBox (VBoxManage list hostonlyifs)"
  type        = string
  default     = "VirtualBox Host-Only Ethernet Adapter" # ⚠️ A ADAPTER selon ta machine
}

# --- Ports exposés pour les services Docker ---

variable "auth_host_port" {
  type        = number
  default     = 5002
}

variable "orders_host_port" {
  type        = number
  default     = 5001
}

variable "gateway_host_port" {
  type        = number
  default     = 5003
}

variable "front_host_port" {
  type        = number
  default     = 5000
}
