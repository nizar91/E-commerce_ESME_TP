terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

############################################################
# Networking (use the default VPC to keep the TP simple)
############################################################
resource "aws_default_vpc" "default" {}

resource "aws_security_group" "db" {
  name        = "ecommerce-db"
  description = "Security group for the shared PostgreSQL database"
  vpc_id      = aws_default_vpc.default.id

  ingress {
    description = "Allow PostgreSQL (tp scope)"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.db_allowed_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

############################################################
# RDS PostgreSQL instance
############################################################
data "aws_subnets" "default_vpc_subnets" {
  filter {
    name   = "vpc-id"
    values = [aws_default_vpc.default.id]
  }
}

resource "aws_db_subnet_group" "db" {
  name        = "ecommerce-db-subnets"
  subnet_ids  = data.aws_subnets.default_vpc_subnets.ids
  description = "Subnet group for the ecommerce PostgreSQL database"
}

resource "aws_db_instance" "ecommerce_db" {
  identifier = "ecommerce-shared-db"

  engine         = "postgres"
  engine_version = "15.7"
  instance_class = "db.t3.micro"

  allocated_storage = 20

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.db.name
  vpc_security_group_ids = [aws_security_group.db.id]

  publicly_accessible = true
  skip_final_snapshot = true
  deletion_protection = false
}
