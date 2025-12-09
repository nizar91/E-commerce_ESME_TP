terraform {
  required_version = ">= 1.5.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
    virtualbox = {
      source  = "terra-farm/virtualbox"
      version = "0.2.2-alpha.1"
    }
  }
}

# Provider Docker (local, via /var/run/docker.sock)
provider "docker" {
  host = "npipe:////./pipe/docker_engine"
}

# Provider VirtualBox
provider "virtualbox" {}

# ---------- 1) VM(S) VIRTUALBOX ----------

resource "virtualbox_vm" "ecom_vm" {
  count = var.vm_count

  name   = format("ecom-vm-%02d", count.index + 1)

  # Image Vagrant Ubuntu (exemple) :
  image = "https://app.vagrantup.com/ubuntu/boxes/bionic64/versions/20180903.0.0/providers/virtualbox.box"

  cpus   = 2
  memory = "1024 mib"

  # Injecter éventuellement du cloud-init (facultatif)
  # user_data = file("${path.module}/user_data")

  network_adapter {
    type           = "hostonly"
    host_interface = "VirtualBox Host-Only Ethernet Adapter"  # ⚠️ À ADAPTER
  }

  status = "running"
}

# ---------- 2) RÉSEAU DOCKER ----------

resource "docker_network" "ecom_net" {
  name = "ecom_net"
}

# ---------- 3) IMAGES DOCKER Pour tes services ----------

resource "docker_image" "auth" {
  name = "ecom_auth:tp"
  build {
    context = "${path.root}/../auth"
  }
}

resource "docker_image" "orders" {
  name = "ecom_orders:tp"
  build {
    context = "${path.root}/../orders"
  }
}

resource "docker_image" "gateway" {
  name = "ecom_gateway:tp"
  build {
    context = "${path.root}/../gateway"
  }
}

resource "docker_image" "front" {
  name = "ecom_front:tp"
  build {
    context = "${path.root}/../front"
  }
}

# ---------- 4) CONTENEURS DOCKER ----------

# Auth (Flask port 5002)
resource "docker_container" "auth" {
  name  = "auth_service"
  image = docker_image.auth.image_id

  networks_advanced {
    name = docker_network.ecom_net.name
  }

  ports {
    internal = 5002
    external = var.auth_host_port
  }

  must_run = true
  restart  = "always"
}

# Orders (Flask port 5001)
resource "docker_container" "orders" {
  name  = "orders_service"
  image = docker_image.orders.image_id

  networks_advanced {
    name = docker_network.ecom_net.name
  }

  ports {
    internal = 5001
    external = var.orders_host_port
  }

  must_run = true
  restart  = "always"
}

# Gateway (Flask port 5003)
resource "docker_container" "gateway" {
  name  = "gateway_service"
  image = docker_image.gateway.image_id

  networks_advanced {
    name = docker_network.ecom_net.name
  }

  ports {
    internal = 5003
    external = var.gateway_host_port
  }

  must_run = true
  restart  = "always"
}

# Front (Flask port 5000)
resource "docker_container" "front" {
  name  = "front_service"
  image = docker_image.front.image_id

  networks_advanced {
    name = docker_network.ecom_net.name
  }

  ports {
    internal = 5000
    external = var.front_host_port
  }

  must_run = true
  restart  = "always"
}
