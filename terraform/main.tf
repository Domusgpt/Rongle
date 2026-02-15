provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# Network (VPC)
# ---------------------------------------------------------------------------
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  version = "5.1.1"

  name = "${var.app_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true # Save costs in dev
}

# ---------------------------------------------------------------------------
# Database (RDS Postgres)
# ---------------------------------------------------------------------------
resource "aws_db_instance" "postgres" {
  identifier           = "${var.app_name}-db"
  engine               = "postgres"
  engine_version       = "15.3"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  username             = var.db_username
  password             = var.db_password
  db_name              = "rongle_db"
  skip_final_snapshot  = true
  publicly_accessible  = false
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.default.name
}

resource "aws_db_subnet_group" "default" {
  name       = "${var.app_name}-db-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "db_sg" {
  name        = "${var.app_name}-db-sg"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}

# ---------------------------------------------------------------------------
# Cache (ElastiCache Redis)
# ---------------------------------------------------------------------------
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.app_name}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.default.name
  security_group_ids   = [aws_security_group.redis_sg.id]
}

resource "aws_elasticache_subnet_group" "default" {
  name       = "${var.app_name}-redis-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis_sg" {
  name        = "${var.app_name}-redis-sg"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}

# ---------------------------------------------------------------------------
# ECS Cluster & Service (Portal)
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"
}

resource "aws_ecs_task_definition" "portal" {
  family                   = "${var.app_name}-portal"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn

  container_definitions = jsonencode([
    {
      name  = "portal"
      image = "${var.ecr_repo_url}:latest"
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
        }
      ]
      environment = [
        { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/rongle_db" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes.0.address}:6379/0" },
        { name = "JWT_SECRET", value = var.jwt_secret },
        { name = "GEMINI_API_KEY", value = var.gemini_api_key }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.app_name}"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "portal"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "portal" {
  name            = "${var.app_name}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.portal.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.ecs_sg.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = "portal"
    container_port   = 8000
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "${var.app_name}-ecs-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "logs" {
  name = "/ecs/${var.app_name}"
}

# ---------------------------------------------------------------------------
# Load Balancer (ALB)
# ---------------------------------------------------------------------------
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "main" {
  name        = "${var.app_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path = "/health"
  }
}

resource "aws_lb_listener" "front_end" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

resource "aws_security_group" "alb_sg" {
  name        = "${var.app_name}-alb-sg"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
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

# ---------------------------------------------------------------------------
# IAM Role
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.app_name}-ecs-execution-role"

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
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
