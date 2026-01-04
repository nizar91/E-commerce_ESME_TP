variable "aws_region" {
  description = "AWS region where the relational database will run"
  type        = string
  default     = "eu-west-3"
}

variable "db_name" {
  description = "Logical database name created in PostgreSQL"
  type        = string
  default     = "ecommerce"
}

variable "db_username" {
  description = "Admin username for the PostgreSQL database"
  type        = string
}

variable "db_password" {
  description = "Admin password for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "db_allowed_cidrs" {
  description = "CIDR blocks allowed to reach PostgreSQL (default: anywhere, tighten for production)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
