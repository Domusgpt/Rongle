output "service_url" {
  value = google_cloud_run_service.portal.status[0].url
}

output "db_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "redis_host" {
  value = google_redis_instance.cache.host
}
