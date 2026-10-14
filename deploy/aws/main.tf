# PIS backend on AWS: ECS Fargate + RDS PostgreSQL 15 + Secrets Manager + CloudWatch. One stack per environment:
#   terraform init -backend-config=<env>.backend.hcl ; terraform apply -var-file=<env>.tfvars
# UNVALIDATED: authored without terraform/AWS access (Phase 15). Run `terraform validate` and `plan` before first apply.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Remote state (S3 + lock table) comes from -backend-config; state and tfvars with real IDs are never committed.
  backend "s3" {}
}

variable "env" { type = string } # staging | production
variable "region" { type = string } # data residency: see docs/adr/0004-aws-hosting.md
variable "vpc_id" { type = string }
variable "private_subnets" { type = list(string) }
variable "public_subnets" { type = list(string) }
variable "image" { type = string } # immutable tag: <acct>.dkr.ecr.<region>.amazonaws.com/pis-api:<git-sha>
variable "certificate_arn" { type = string }
variable "auth_issuer" { type = string }
variable "auth_audience" { type = string }
variable "auth_jwks_url" { type = string }
variable "alarm_email" { type = string }
variable "monthly_budget_usd" { type = number }
variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

provider "aws" { region = var.region }

locals {
  name = "pis-${var.env}"
}

# ---- Network: only the ALB reaches the API; only the API/migrate task reaches the DB ----
resource "aws_security_group" "alb" {
  name   = "${local.name}-alb"
  vpc_id = var.vpc_id
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "app" {
  name   = "${local.name}-app"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress { # IdP JWKS, GitHub API, ECR, Secrets Manager, CloudWatch
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db" {
  name   = "${local.name}-db"
  vpc_id = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

# ---- Database: private, encrypted, 14-day point-in-time backups ----
resource "aws_db_subnet_group" "db" {
  name       = local.name
  subnet_ids = var.private_subnets
}

resource "aws_db_instance" "db" {
  identifier                      = local.name
  engine                          = "postgres"
  engine_version                  = "15"
  instance_class                  = var.db_instance_class
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_encrypted               = true
  db_name                         = "pis_db"
  username                        = "pis_admin"
  manage_master_user_password     = true # master secret lives in Secrets Manager, never in state/tfvars
  db_subnet_group_name            = aws_db_subnet_group.db.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  publicly_accessible             = false
  multi_az                        = var.env == "production"
  backup_retention_period         = 14
  backup_window                   = "02:00-03:00"
  deletion_protection             = var.env == "production"
  skip_final_snapshot             = var.env != "production"
  final_snapshot_identifier       = var.env == "production" ? "${local.name}-final" : null
  enabled_cloudwatch_logs_exports = ["postgresql"]
}

# ---- Secrets: containers only; values are set out-of-band (runbook) so they never touch source or state ----
resource "aws_secretsmanager_secret" "database_url" { name = "${local.name}/DATABASE_URL" }
resource "aws_secretsmanager_secret" "github_token" { name = "${local.name}/GITHUB_TOKEN" }

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "exec" {
  name               = "${local.name}-exec"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy_attachment" "exec" {
  role       = aws_iam_role.exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "read_secrets" {
  role = aws_iam_role.exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = [aws_secretsmanager_secret.database_url.arn, aws_secretsmanager_secret.github_token.arn]
    }]
  })
}

resource "aws_iam_role" "task" { # the app itself needs no AWS permissions
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/pis/${var.env}"
  retention_in_days = 30
}

# ---- Task definitions: one immutable image; migrate overrides the command (controlled release step) ----
locals {
  common = {
    image     = var.image
    essential = true
    environment = [
      { name = "APP_ENV", value = var.env },
      { name = "AUTH_ISSUER", value = var.auth_issuer },
      { name = "AUTH_AUDIENCE", value = var.auth_audience },
      { name = "AUTH_JWKS_URL", value = var.auth_jwks_url },
      { name = "SEED_DEMO_DATA", value = "false" },
      { name = "LEETCODE_INTEGRATION_ENABLED", value = "false" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
      { name = "GITHUB_TOKEN", valueFrom = aws_secretsmanager_secret.github_token.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "pis"
      }
    }
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.exec.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([merge(local.common, {
    name         = "api"
    portMappings = [{ containerPort = 8000 }]
    stopTimeout  = 30
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request as u;u.urlopen('http://localhost:8000/health')\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  })])
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${local.name}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.exec.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([merge(local.common, {
    name    = "migrate"
    command = ["python", "-m", "ingest.migrate"]
  })])
}

# ---- Load balancer + service (rolling deploy; circuit breaker rolls back a failing release) ----
resource "aws_lb" "alb" {
  name               = local.name
  subnets            = var.public_subnets
  security_groups    = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = local.name
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/health/ready"
    matcher             = "200"
    interval            = 15
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_cluster" "c" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_service" "api" {
  name                               = "api"
  cluster                            = aws_ecs_cluster.c.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.env == "production" ? 2 : 1
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets         = var.private_subnets
    security_groups = [aws_security_group.app.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.https]
}

# ---- Alerts ----
resource "aws_sns_topic" "alerts" { name = "${local.name}-alerts" }

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "unhealthy" {
  alarm_name          = "${local.name}-no-healthy-targets"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HealthyHostCount"
  dimensions          = { TargetGroup = aws_lb_target_group.api.arn_suffix, LoadBalancer = aws_lb.alb.arn_suffix }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "errors_5xx" {
  alarm_name          = "${local.name}-5xx"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = aws_lb.alb.arn_suffix }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 10
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "latency" {
  alarm_name          = "${local.name}-p95-latency"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  dimensions          = { LoadBalancer = aws_lb.alb.arn_suffix }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 2
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "db_connections" {
  alarm_name          = "${local.name}-db-connections"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.db.identifier }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanThreshold"
  threshold           = 60
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "db_storage" {
  alarm_name          = "${local.name}-db-free-storage"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.db.identifier }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "LessThanThreshold"
  threshold           = 3000000000
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# Repeated sync failures: services/sync.py logs msg=sync_finished with sync_status.
resource "aws_cloudwatch_log_metric_filter" "sync_failed" {
  name           = "${local.name}-sync-failed"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = "{ $.msg = \"sync_finished\" && $.sync_status = \"failed\" }"
  metric_transformation {
    name      = "SyncFailed"
    namespace = "PIS/${var.env}"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "sync_failed" {
  alarm_name          = "${local.name}-sync-failures"
  namespace           = "PIS/${var.env}"
  metric_name         = "SyncFailed"
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# RDS backup/failure events go to the same topic (covers backup failure alerting).
resource "aws_db_event_subscription" "backup" {
  name             = "${local.name}-backup"
  sns_topic        = aws_sns_topic.alerts.arn
  source_type      = "db-instance"
  source_ids       = [aws_db_instance.db.identifier]
  event_categories = ["backup", "failure", "recovery"]
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }
}

output "alb_dns_name" { value = aws_lb.alb.dns_name }
output "db_endpoint" { value = aws_db_instance.db.address }
