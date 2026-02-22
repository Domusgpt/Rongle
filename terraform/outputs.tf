output "vpc_id" {
  value = module.vpc.vpc_id
}

output "db_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes.0.address
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}
