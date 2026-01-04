output "rds_endpoint" {
  description = "Endpoint (hostname) of the PostgreSQL database"
  value       = aws_db_instance.ecommerce_db.address
}

output "rds_port" {
  description = "Database port exposed by RDS"
  value       = aws_db_instance.ecommerce_db.port
}

output "rds_db_name" {
  description = "Logical database created on the RDS instance"
  value       = aws_db_instance.ecommerce_db.db_name
}

output "rds_username" {
  description = "Admin user configured for PostgreSQL"
  value       = var.db_username
}

output "rds_password" {
  description = "Admin password (sensitive) for PostgreSQL"
  value       = var.db_password
  sensitive   = true
}
