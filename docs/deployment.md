# HBI System Deployment Guide

This guide covers the deployment and operational aspects of the Hybrid Book Index (HBI) system, including local development, production deployment, and scaling considerations.

## Architecture Overview

The HBI system consists of multiple interconnected services:

- **API Service**: FastAPI application handling HTTP requests
- **Worker Service**: Background task processing with Redis/arq
- **Text Index**: SQLite with FTS5 for lexical search
- **Object Store**: MinIO for file storage
- **Graph Database**: Neo4j for ToC and index relationships
- **Vector Store**: sqlite-vec for semantic search
- **Observability Stack**: Prometheus, Loki, Grafana, Langfuse

## Local Development Setup

### Prerequisites

- Docker and Docker Compose (latest versions)
- Python 3.11+ (for local development)
- Git (for version control)
- 8GB+ RAM recommended
- 20GB+ free disk space

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd hbi-system
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Verify services are running:**
   ```bash
   docker-compose ps
   ```

4. **Check service health:**
   ```bash
   curl http://localhost:8000/health
   ```

### Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000 | Main application |
| Grafana | http://localhost:3000 | Monitoring dashboards |
| MinIO Console | http://localhost:9001 | Object storage UI |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| Prometheus | http://localhost:9090 | Metrics collection |
| Langfuse | http://localhost:3001 | LLM tracing |

## Production Deployment

### Infrastructure Requirements

#### Minimum Specifications
- **CPU**: 4 cores
- **RAM**: 16GB
- **Storage**: 100GB SSD
- **Network**: 1Gbps connection

#### Recommended Specifications
- **CPU**: 8+ cores
- **RAM**: 32GB+
- **Storage**: 500GB+ NVMe SSD
- **Network**: 10Gbps connection

### Docker Compose Production Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  # API Service
  app:
    image: hbi-api:latest
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=sqlite:///./data/database/prod.db
      - MINIO_ENDPOINT=minio:9000
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      - redis
      - minio
      - neo4j
    restart: unless-stopped

  # Worker Service
  worker:
    image: hbi-worker:latest
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - minio
      - neo4j
    restart: unless-stopped

  # Redis (Task Queue)
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  # MinIO (Object Storage)
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    environment:
      - MINIO_ROOT_USER=${MINIO_ROOT_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
    command: server /data --console-address ":9001"
    restart: unless-stopped

  # Neo4j (Graph Database)
  neo4j:
    image: neo4j:latest
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["graph-data-science","apoc"]
    restart: unless-stopped

  # Observability Stack
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  grafana:
    image: grafana/grafana-oss:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana-datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    depends_on:
      - prometheus
      - loki
    restart: unless-stopped

volumes:
  redis_data:
  minio_data:
  neo4j_data:
  neo4j_logs:
  grafana_data:
```

### Environment Variables

Create `.env.prod` file:

```bash
# Application
ENVIRONMENT=production
DEBUG=false

# Redis
REDIS_URL=redis://redis:6379

# MinIO
MINIO_ROOT_USER=your_secure_minio_user
MINIO_ROOT_PASSWORD=your_secure_minio_password
MINIO_ENDPOINT=minio:9000

# Neo4j
NEO4J_PASSWORD=your_secure_neo4j_password

# Grafana
GRAFANA_PASSWORD=your_secure_grafana_password

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Security
SECRET_KEY=your_secret_key_for_jwt
```

### Deployment Steps

1. **Prepare environment:**
   ```bash
   cp .env.prod .env
   # Edit .env with production values
   ```

2. **Build and deploy:**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Verify deployment:**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   curl http://localhost:8000/health
   ```

4. **Initialize databases:**
   ```bash
   docker-compose -f docker-compose.prod.yml exec app python -c "from src.core.database import initialize_database; initialize_database()"
   ```

## Scaling Considerations

### Horizontal Scaling

#### API Service Scaling
```yaml
services:
  app:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

#### Worker Service Scaling
```yaml
services:
  worker:
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '2.0'
          memory: 8G
```

### Database Scaling

#### SQLite Limitations
- Single-writer limitation
- File-based storage
- Not suitable for high-concurrency scenarios

#### Migration to PostgreSQL (Future)
```yaml
services:
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=hbi
      - POSTGRES_USER=hbi_user
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  pgvector:
    image: pgvector/pgvector:pg15
    # For vector storage migration
```

### Redis Cluster (High Availability)

```yaml
services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes

  redis-replica:
    image: redis:7-alpine
    command: redis-server --slaveof redis-master 6379 --appendonly yes
    depends_on:
      - redis-master
```

## Monitoring and Observability

### Key Metrics to Monitor

#### Application Metrics
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Background job queue length
- Document processing times

#### System Metrics
- CPU and memory usage
- Disk I/O and space
- Network throughput
- Database connection pools

#### Business Metrics
- Documents processed per hour
- Query success rates
- User satisfaction scores
- API usage patterns

### Grafana Dashboards

#### System Overview Dashboard
- Service health status
- Resource utilization
- Error rates and trends
- Background job statistics

#### Performance Dashboard
- API response times
- Database query performance
- Cache hit rates
- LLM API usage and costs

#### Business Dashboard
- Document upload trends
- Query volume and types
- User engagement metrics
- Quality gate pass/fail rates

### Alerting Rules

```yaml
# Prometheus alerting rules
groups:
  - name: hbi_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: QueueBacklog
        expr: arq_queue_length > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Background job queue backlog"

      - alert: LowDiskSpace
        expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space"
```

## Backup and Recovery

### Data Backup Strategy

#### Database Backups
```bash
# SQLite backup
docker-compose exec text_index sqlite3 /db/hbi.db ".backup /db/backup_$(date +%Y%m%d_%H%M%S).db"

# Neo4j backup
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups

# Redis backup (RDB files are automatic with appendonly yes)
```

#### File Storage Backup
```bash
# MinIO backup
mc mirror --overwrite hbi-minio/buckets /backups/minio/$(date +%Y%m%d)
```

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Database backups
docker-compose exec -T text_index sqlite3 /db/hbi.db ".backup $BACKUP_DIR/hbi.db"
docker-compose exec -T neo4j neo4j-admin database dump neo4j --to-path=$BACKUP_DIR

# MinIO backup
mc mirror --overwrite hbi-minio/buckets $BACKUP_DIR/minio

# Compress and cleanup
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

# Retention policy (keep last 7 days)
find /backups -name "*.tar.gz" -mtime +7 -delete
```

### Recovery Procedures

#### Complete System Recovery
1. Stop all services
2. Restore databases from backups
3. Restore MinIO data
4. Restart services
5. Verify system health

#### Partial Recovery
1. Identify affected components
2. Restore specific data
3. Test functionality
4. Monitor for issues

## Security Considerations

### Network Security

#### Firewall Configuration
```bash
# Allow only necessary ports
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw allow 8000/tcp    # API
ufw default deny incoming
ufw default allow outgoing
```

#### SSL/TLS Configuration
```yaml
services:
  app:
    environment:
      - SSL_CERT_PATH=/etc/ssl/certs/hbi.crt
      - SSL_KEY_PATH=/etc/ssl/private/hbi.key
    volumes:
      - ./ssl:/etc/ssl
```

### Access Control

#### API Authentication (Future Enhancement)
- JWT token-based authentication
- Role-based access control
- API key management

#### Database Security
- Strong passwords for all services
- Network isolation between services
- Regular password rotation

### Data Protection

#### Encryption at Rest
- MinIO server-side encryption
- Database encryption (when using PostgreSQL)
- Encrypted backups

#### Encryption in Transit
- TLS for all external communications
- Internal service communication encryption
- Secure Redis connections

## Performance Tuning

### Application Tuning

#### FastAPI Configuration
```python
app = FastAPI(
    title="HBI System",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Worker configuration
workers = multiprocessing.cpu_count()
```

#### Database Optimization
```sql
-- SQLite optimizations
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  -- 64MB cache
PRAGMA temp_store=MEMORY;
```

### System Tuning

#### Linux Kernel Parameters
```bash
# /etc/sysctl.conf
vm.max_map_count=262144
net.core.somaxconn=65536
fs.file-max=2097152
```

#### Docker Configuration
```json
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## Troubleshooting Production Issues

### Common Issues and Solutions

#### High Memory Usage
**Symptoms:** Container restarts, slow responses
**Solutions:**
- Increase memory limits
- Optimize Python garbage collection
- Monitor memory leaks
- Implement memory profiling

#### Slow Database Queries
**Symptoms:** High query latency, timeouts
**Solutions:**
- Add database indexes
- Optimize query patterns
- Implement query caching
- Consider read replicas

#### Background Job Failures
**Symptoms:** Jobs stuck in queue, DLQ growing
**Solutions:**
- Check worker logs
- Verify resource availability
- Review error handling
- Implement circuit breakers

### Log Analysis

#### Centralized Logging
```yaml
services:
  app:
    logging:
      driver: "loki"
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
```

#### Log Queries
```bash
# Query application logs
docker-compose logs app | grep ERROR

# Query worker logs
docker-compose logs worker | grep "failed"

# Search for specific patterns
docker-compose logs | grep "sanitization"
```

## Cost Optimization

### Resource Optimization

#### Right-sizing Containers
- Monitor actual resource usage
- Adjust CPU and memory limits
- Use horizontal scaling for variable loads

#### Storage Optimization
- Implement data lifecycle policies
- Compress old logs and backups
- Use appropriate storage classes

### Cloud Cost Management

#### Spot Instances (AWS)
```yaml
services:
  worker:
    deploy:
      placement:
        constraints:
          - node.labels.instance-type==spot
```

#### Auto-scaling
- Scale based on queue length
- Scale based on CPU utilization
- Implement cooldown periods

## Maintenance Procedures

### Regular Maintenance Tasks

#### Weekly Tasks
- Review error logs
- Check disk space usage
- Verify backup integrity
- Update security patches

#### Monthly Tasks
- Full system backup verification
- Performance benchmark testing
- Security vulnerability scanning
- Dependency updates

#### Quarterly Tasks
- Major version upgrades
- Architecture review
- Capacity planning
- Disaster recovery testing

### Update Procedures

#### Rolling Updates
```bash
# Update with zero downtime
docker-compose up -d --scale app=2
docker-compose up -d --scale app=1
```

#### Blue-Green Deployment
1. Deploy new version alongside current
2. Test new version thoroughly
3. Switch traffic to new version
4. Keep old version as rollback option

## Compliance and Governance

### Data Retention Policies

#### Log Retention
```yaml
# Loki configuration
table_manager:
  retention_deletes_enabled: true
  retention_period: 30d
```

#### Document Retention
- Implement automatic cleanup
- Archive old documents
- Maintain audit trails

### Audit Logging

#### Security Events
- Authentication attempts
- Configuration changes
- Data access patterns
- Security incidents

#### Compliance Reporting
- Generate monthly reports
- Track system changes
- Maintain change logs
- Document incidents

This deployment guide provides a comprehensive foundation for operating the HBI system in production environments, with considerations for scalability, security, monitoring, and maintenance.