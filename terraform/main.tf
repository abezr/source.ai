terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "hbi-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "hbi-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC and Networking
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "hbi-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  enable_vpn_gateway = false

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# Security Groups
resource "aws_security_group" "alb" {
  name_prefix = "hbi-alb-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

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

  tags = {
    Name        = "hbi-alb-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "ecs" {
  name_prefix = "hbi-ecs-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "hbi-ecs-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "hbi-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "hbi-rds-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "hbi-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "hbi-redis-sg"
    Environment = var.environment
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "hbi" {
  name = "hbi-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_ecs_cluster_capacity_providers" "hbi" {
  cluster_name       = aws_ecs_cluster.hbi.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "hbi_api" {
  family                   = "hbi-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "hbi-api"
      image = "${aws_ecr_repository.hbi_api.repository_url}:latest"
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.langfuse.username}:${aws_db_instance.langfuse.password}@${aws_db_instance.langfuse.endpoint}/${aws_db_instance.langfuse.db_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
        },
        {
          name  = "S3_BUCKET"
          value = aws_s3_bucket.hbi.bucket
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/hbi-api"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# ECS Service
resource "aws_ecs_service" "hbi_api" {
  name            = "hbi-api-service"
  cluster         = aws_ecs_cluster.hbi.id
  task_definition = aws_ecs_task_definition.hbi_api.arn
  desired_count   = 2

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.hbi_api.arn
    container_name   = "hbi-api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.hbi_api]

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# RDS PostgreSQL for Langfuse
resource "aws_db_instance" "langfuse" {
  identifier             = "hbi-langfuse"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp2"
  db_name                = "langfuse"
  username               = var.db_username
  password               = var.db_password
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.hbi.name
  skip_final_snapshot    = true

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_db_subnet_group" "hbi" {
  name       = "hbi-db-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "hbi-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.hbi.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_elasticache_subnet_group" "hbi" {
  name       = "hbi-redis-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# S3 Bucket for Object Storage
resource "aws_s3_bucket" "hbi" {
  bucket = "hbi-object-storage-${random_string.bucket_suffix.result}"

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_s3_bucket_versioning" "hbi" {
  bucket = aws_s3_bucket.hbi.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "hbi" {
  bucket = aws_s3_bucket.hbi.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  lower   = true
  upper   = false
  numeric = true
  special = false
}

# Application Load Balancer
resource "aws_lb" "hbi_api" {
  name               = "hbi-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_lb_target_group" "hbi_api" {
  name        = "hbi-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_lb_listener" "hbi_api" {
  load_balancer_arn = aws_lb.hbi_api.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.hbi_api.arn
  }
}

# Route 53 (assuming a domain is provided)
resource "aws_route53_zone" "hbi" {
  name = var.domain_name

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_route53_record" "hbi_api" {
  zone_id = aws_route53_zone.hbi.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.hbi_api.dns_name
    zone_id                = aws_lb.hbi_api.zone_id
    evaluate_target_health = true
  }
}

# IAM Roles
resource "aws_iam_role" "ecs_execution" {
  name = "hbi-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "hbi-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "hbi-ecs-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.hbi.arn}/*"
      },
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# ECR Repository
resource "aws_ecr_repository" "hbi_api" {
  name                 = "hbi-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "hbi_api" {
  name              = "/ecs/hbi-api"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    Project     = "HBI"
  }
}