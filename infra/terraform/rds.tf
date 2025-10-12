# RDS Subnet Group (default VPC subnets)
resource "aws_db_subnet_group" "fraud_db_subnet" {
  name       = "${local.db_name}-subnet-group"
  subnet_ids = data.aws_subnets.default.ids  # Data source below

  tags = {
    Name = "${local.db_name}-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "fraud_db" {
  identifier             = local.db_name
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100  # Auto-scale
  storage_type           = "gp2"
  storage_encrypted      = true
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.fraud_db_subnet.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  publicly_accessible    = var.environment == "dev" ? true : false  # Public for dev
  multi_az               = var.environment == "prod" ? true : false
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"
  skip_final_snapshot    = true  # Dev only; false for prod

  # Parameter group for Postgres
  parameter_group_name = aws_db_parameter_group.fraud_db_params.name

  tags = {
    Name = local.db_name
  }
}

# Security Group for RDS (inbound from Lambda/ECS)
resource "aws_security_group" "rds_sg" {
  name_prefix = "${local.db_name}-sg-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Restrict to VPC/Lambda SG in prod
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.db_name}-sg"
  }
}

# DB Parameter Group (Postgres tweaks)
resource "aws_db_parameter_group" "fraud_db_params" {
  name   = "${local.db_name}-params"
  family = "postgres15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "rds.log_retention_period"
    value = "1440"  # 1 day
  }

  tags = {
    Name = "${local.db_name}-params"
  }
}

# Data sources (default VPC/subnets)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}