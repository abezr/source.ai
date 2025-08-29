# HBI System Troubleshooting Guide

This guide provides solutions for common issues encountered when operating the Hybrid Book Index (HBI) system, with a focus on Sprint 4 features and new components.

## Quick Reference

### Emergency Contacts
- **System Admin**: admin@company.com
- **DevOps Team**: devops@company.com
- **Security Team**: security@company.com

### Critical Commands
```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs [service_name]

# Restart services
docker-compose restart [service_name]

# Check system health
curl http://localhost:8000/health

# Check queue status
docker-compose exec redis redis-cli LLEN arq:queue
```

## Service Health Issues

### API Service Unhealthy

**Symptoms:**
- `curl http://localhost:8000/health` returns errors
- API endpoints return 500 errors
- Application logs show startup failures

**Diagnosis:**
```bash
# Check API service logs
docker-compose logs app

# Check if service is running
docker-compose ps app

# Check resource usage
docker-compose exec app ps aux
```

**Common Causes & Solutions:**

#### Database Connection Issues
```bash
# Check SQLite database
docker-compose exec text_index sqlite3 /db/hbi.db ".tables"

# Check Neo4j connection
docker-compose exec neo4j cypher-shell -u neo4j -p neo4jpassword "MATCH () RETURN count(*) LIMIT 1;"

# Restart database services
docker-compose restart text_index neo4j
```

#### Redis Connection Issues
```bash
# Check Redis connectivity
docker-compose exec redis redis-cli ping

# Check Redis memory usage
docker-compose exec redis redis-cli info memory

# Clear Redis data (CAUTION: This will clear all queues)
docker-compose exec redis redis-cli FLUSHALL
```

#### Configuration Issues
```bash
# Check environment variables
docker-compose exec app env | grep -E "(REDIS|DATABASE|MINIO|NEO4J)"

# Validate configuration
curl http://localhost:8000/config
```

### Worker Service Issues

**Symptoms:**
- Background jobs not processing
- Queue length growing
- Files stuck in "processing" state

**Diagnosis:**
```bash
# Check worker logs
docker-compose logs worker

# Check queue length
docker-compose exec redis redis-cli LLEN arq:queue

# Check active jobs
docker-compose exec redis redis-cli KEYS "arq:*"
```

**Solutions:**

#### Worker Not Starting
```bash
# Check worker dependencies
docker-compose ps redis minio neo4j

# Restart worker
docker-compose restart worker

# Check worker configuration
docker-compose exec worker cat /app/src/core/worker.py | head -20
```

#### Job Processing Failures
```bash
# Check Dead Letter Queue
docker-compose exec redis redis-cli LLEN dlq:book_processing

# View failed jobs
docker-compose exec redis redis-cli LRANGE dlq:book_processing 0 10

# Clear DLQ (after investigation)
docker-compose exec redis redis-cli DEL dlq:book_processing
```

#### Resource Constraints
```bash
# Check worker memory usage
docker-compose exec worker ps aux

# Check available system resources
docker system df

# Scale worker instances
docker-compose up -d --scale worker=3
```

## Document Processing Issues

### File Upload Failures

**Symptoms:**
- Upload endpoint returns errors
- Files not appearing in MinIO
- Background processing not triggered

**Diagnosis:**
```bash
# Check MinIO service
docker-compose ps minio

# Check MinIO logs
docker-compose logs minio

# Verify MinIO connectivity
curl http://localhost:9000/minio/health/live
```

**Solutions:**

#### MinIO Connection Issues
```bash
# Check MinIO credentials
docker-compose exec app env | grep MINIO

# Test MinIO connection
docker-compose exec app python -c "
from src.core.object_store import get_object_store_client
client = get_object_store_client()
print('MinIO connection successful')
"
```

#### File Type Validation
```bash
# Check supported file types
curl -X POST http://localhost:8000/books/1/upload \
  -F "file=@invalid_file.txt"

# Response should indicate supported formats
# Supported: PDF (.pdf), DjVu (.djvu, .djv)
```

#### Storage Space Issues
```bash
# Check MinIO disk usage
docker-compose exec minio df -h /data

# Check MinIO bucket size
docker-compose exec minio mc ls hbi-minio/books/
```

### Text Extraction Failures

**Symptoms:**
- PDF/DjVu text extraction fails
- Empty or corrupted text content
- Processing timeouts

**Diagnosis:**
```bash
# Check parser logs
docker-compose logs app | grep "extraction\|parser"

# Test text extraction manually
docker-compose exec app python -c "
from src.agents.parser import extract_text_from_pdf
result = extract_text_from_pdf('/path/to/test.pdf')
print(f'Extracted {len(result)} characters')
"
```

**Solutions:**

#### PDF Extraction Issues
```bash
# Check PyMuPDF installation
docker-compose exec app python -c "import fitz; print(fitz.__version__)"

# Test with sample PDF
docker-compose exec app python -c "
import fitz
doc = fitz.open('/path/to/sample.pdf')
print(f'Pages: {doc.page_count}')
text = doc.load_page(0).get_text()
print(f'Text length: {len(text)}')
"
```

#### DjVu Extraction Issues
```bash
# Check djvulibre installation
docker-compose exec app which djvutxt

# Test DjVu extraction
docker-compose exec app djvutxt /path/to/sample.djvu | head -20

# Check file permissions
docker-compose exec app ls -la /path/to/sample.djvu
```

#### OCR Requirements
```bash
# For scanned documents, ensure text is selectable
# If OCR is needed, preprocess documents before upload
# Check document quality and resolution
```

### Table of Contents Issues

**Symptoms:**
- ToC parsing fails or returns empty results
- Incorrect hierarchical structure
- Missing page numbers

**Diagnosis:**
```bash
# Check ToC parsing logs
docker-compose logs app | grep "toc\|TOC"

# Test ToC extraction
curl http://localhost:8000/books/1/toc
```

**Solutions:**

#### LLM Parsing Issues
```bash
# Check LLM client configuration
docker-compose exec app env | grep -E "(OPENAI|ANTHROPIC)"

# Test LLM connectivity
docker-compose exec app python -c "
from src.core.llm_client import get_llm_client
client = get_llm_client()
response = client.generate_grounded_answer('test query', 'test context')
print('LLM connection successful')
"
```

#### Sanitization Issues
```bash
# Check sanitization logs
docker-compose logs app | grep "sanitiz"

# Test text sanitization
docker-compose exec app python -c "
from src.core.sanitizer import sanitize_text_for_llm
result = sanitize_text_for_llm('Test text with ## markdown')
print(f'Sanitized: {result}')
"
```

#### Neo4j Storage Issues
```bash
# Check Neo4j connection
docker-compose exec neo4j cypher-shell -u neo4j -p neo4jpassword \
  "MATCH (b:Book {id: 1}) RETURN b;"

# Check graph data
docker-compose exec neo4j cypher-shell -u neo4j -p neo4jpassword \
  "MATCH (b:Book {id: 1})-[:HAS_TOC]->(t:TOCSection) RETURN count(t);"
```

### Index Processing Issues

**Symptoms:**
- Alphabetical index not found or parsed incorrectly
- Index terms missing or malformed
- Page references incorrect

**Diagnosis:**
```bash
# Check index processing logs
docker-compose logs app | grep "index\|Index"

# Test index parsing
docker-compose exec app python -c "
from src.agents.parser import parse_index_from_text
result = parse_index_from_text('A\nApple 5, 10\nB\nBanana 15')
print(f'Parsed {len(result)} index entries')
"
```

**Solutions:**

#### Index Detection Issues
```bash
# Check page identification heuristic
docker-compose exec app python -c "
from src.agents.parser import identify_index_pages
pages = identify_index_pages('Sample text with index at end', 100)
print(f'Identified index pages: {pages}')
"
```

#### LLM Index Parsing Issues
```bash
# Test LLM index parsing
docker-compose exec app python -c "
from src.core.llm_client import get_llm_client
client = get_llm_client()
result = client.get_structured_index('A\nApple 5, 10\nB\nBanana 15')
print(f'LLM parsed: {result}')
"
```

#### Graph Storage Issues
```bash
# Check index graph data
docker-compose exec neo4j cypher-shell -u neo4j -p neo4jpassword \
  "MATCH (b:Book {id: 1})-[:HAS_INDEX]->(i:IndexTerm) RETURN count(i);"

# Check index relationships
docker-compose exec neo4j cypher-shell -u neo4j -p neo4jpassword \
  "MATCH (i:IndexTerm)-[r:APPEARS_ON_PAGE]->(p:Page) RETURN i.term, r.page_number LIMIT 10;"
```

## Query and Search Issues

### Retrieval Problems

**Symptoms:**
- Queries return no results
- Irrelevant results returned
- Slow query performance

**Diagnosis:**
```bash
# Check query logs
docker-compose logs app | grep "query\|retrieval"

# Test hybrid search
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "book_id": 1}'
```

**Solutions:**

#### Embedding Issues
```bash
# Check embedding generation
docker-compose exec app python -c "
from src.agents.parser import generate_embeddings_for_chunks
embeddings = generate_embeddings_for_chunks([{'chunk_text': 'test', 'page_number': 1, 'chunk_order': 0}])
print(f'Generated {len(embeddings)} embeddings')
"
```

#### Vector Search Issues
```bash
# Check vector store
docker-compose exec text_index sqlite3 /db/hbi.db \
  "SELECT count(*) FROM chunks WHERE embedding IS NOT NULL;"

# Test vector similarity
docker-compose exec app python -c "
from src.core.vector_store import get_vector_store_client
client = get_vector_store_client()
results = client.search_similar('test query', top_k=5)
print(f'Found {len(results)} similar chunks')
"
```

#### Lexical Search Issues
```bash
# Check FTS5 index
docker-compose exec text_index sqlite3 /db/hbi.db \
  "SELECT * FROM chunks_fts WHERE chunk_text MATCH 'test*';"

# Rebuild FTS index if corrupted
docker-compose exec text_index sqlite3 /db/hbi.db "REINDEX chunks_fts;"
```

### Quality Gate Issues

**Symptoms:**
- All queries return fallback messages
- High fallback rate in logs
- Quality gates too restrictive

**Diagnosis:**
```bash
# Check current configuration
curl http://localhost:8000/config

# Check fallback logs
docker-compose logs app | grep "fallback\|gate"
```

**Solutions:**

#### Retrieval Gate Issues
```bash
# Check minimum chunks configuration
curl http://localhost:8000/config | jq '.min_chunks'

# Adjust configuration
curl -X PUT http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{"min_chunks": 1}'
```

#### Generation Gate Issues
```bash
# Check confidence threshold
curl http://localhost:8000/config | jq '.confidence_threshold'

# Adjust for more lenient quality control
curl -X PUT http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{"confidence_threshold": 0.3}'
```

## Configuration Issues

### Dynamic Configuration Problems

**Symptoms:**
- Configuration changes not taking effect
- Configuration API returns errors
- Thread safety issues

**Diagnosis:**
```bash
# Check configuration store
docker-compose exec app python -c "
from src.core.config_store import get_rag_config
config = get_rag_config()
print(f'Current config: {config.dict()}')
"
```

**Solutions:**

#### Configuration Persistence
```bash
# Configuration is in-memory only
# Changes lost on restart - this is by design
# For persistent config, implement database storage
```

#### Validation Errors
```bash
# Test configuration validation
curl -X PUT http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{"retrieval_top_k": -1}'

# Should return validation error
```

## Security Issues

### Sanitization Problems

**Symptoms:**
- Sanitization blocking legitimate content
- Security patterns not being caught
- Performance impact from sanitization

**Diagnosis:**
```bash
# Check sanitization logs
docker-compose logs app | grep "sanitiz"

# Test sanitization
docker-compose exec app python -c "
from src.core.sanitizer import sanitize_text_for_llm
result = sanitize_text_for_llm('Test content ## with markdown')
print(f'Original: Test content ## with markdown')
print(f'Sanitized: {result}')
"
```

**Solutions:**

#### False Positives
```bash
# Adjust sanitization rules if needed
# Review legitimate content being blocked
# Consider context-specific sanitization
```

#### Performance Issues
```bash
# Check sanitization performance
docker-compose exec app python -c "
import time
from src.core.sanitizer import sanitize_text_for_llm

start = time.time()
result = sanitize_text_for_llm('Large text content' * 1000)
end = time.time()
print(f'Sanitization took {end - start:.2f} seconds')
"
```

## Performance Issues

### System Performance

**Symptoms:**
- Slow response times
- High CPU/memory usage
- Service timeouts

**Diagnosis:**
```bash
# Check system resources
docker stats

# Check service-specific metrics
docker-compose exec app ps aux

# Check database performance
docker-compose exec text_index sqlite3 /db/hbi.db ".timer on" "SELECT count(*) FROM chunks;"
```

**Solutions:**

#### Database Optimization
```bash
# Add indexes if needed
docker-compose exec text_index sqlite3 /db/hbi.db "
CREATE INDEX IF NOT EXISTS idx_chunks_book_id ON chunks(book_id);
CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(page_number);
"

# Optimize SQLite settings
docker-compose exec text_index sqlite3 /db/hbi.db "
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;
"
```

#### Memory Optimization
```bash
# Adjust Docker memory limits
# Update docker-compose.yml with appropriate limits
services:
  app:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

#### Caching Strategies
```bash
# Implement Redis caching for frequent queries
# Cache embeddings for repeated content
# Cache LLM responses for identical queries
```

### Network Issues

**Symptoms:**
- Service communication failures
- Timeout errors
- Connection refused errors

**Diagnosis:**
```bash
# Check network connectivity
docker-compose exec app ping redis

# Check service discovery
docker-compose exec app nslookup redis

# Check firewall rules
sudo ufw status
```

**Solutions:**

#### Service Dependencies
```bash
# Ensure services start in correct order
docker-compose up -d redis
docker-compose up -d minio neo4j text_index
docker-compose up -d app worker
```

#### Network Configuration
```yaml
# Update docker-compose.yml with proper networking
services:
  app:
    depends_on:
      - redis
      - minio
      - neo4j
      - text_index
    networks:
      - hbi_network

networks:
  hbi_network:
    driver: bridge
```

## Monitoring and Alerting

### Setting Up Alerts

#### Prometheus Alert Rules
```yaml
# /config/prometheus/alert_rules.yml
groups:
  - name: hbi_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical

      - alert: QueueBacklog
        expr: arq_queue_length > 100
        for: 10m
        labels:
          severity: warning

      - alert: LowDiskSpace
        expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) > 0.85
        for: 5m
        labels:
          severity: warning
```

#### Grafana Dashboards

**Key Metrics to Monitor:**
- API response times and error rates
- Background job queue length and processing times
- Database query performance
- System resource utilization
- LLM API usage and costs

### Log Analysis

#### Centralized Logging
```bash
# View all service logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# Search for specific errors
docker-compose logs | grep ERROR

# Analyze log patterns
docker-compose logs | grep "sanitiz" | head -20
```

#### Log Rotation
```yaml
# Ensure proper log rotation
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Data Recovery

### Database Recovery

#### SQLite Recovery
```bash
# Backup current database
docker-compose exec text_index sqlite3 /db/hbi.db ".backup /db/backup.db"

# Restore from backup
docker-compose exec text_index sqlite3 /db/hbi.db ".restore /db/backup.db"
```

#### Neo4j Recovery
```bash
# Backup Neo4j data
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups

# Restore Neo4j data
docker-compose exec neo4j neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
```

### File Recovery

#### MinIO Recovery
```bash
# List all objects
docker-compose exec minio mc ls hbi-minio/books/

# Download specific file
docker-compose exec minio mc cp hbi-minio/books/file.pdf /tmp/

# Restore from backup
docker-compose exec minio mc mirror /backups/minio hbi-minio/books/
```

## Preventive Maintenance

### Regular Tasks

#### Daily Checks
```bash
# Health check
curl http://localhost:8000/health

# Queue monitoring
docker-compose exec redis redis-cli LLEN arq:queue

# Disk space monitoring
df -h
```

#### Weekly Tasks
```bash
# Log rotation check
docker-compose logs | wc -l

# Database integrity check
docker-compose exec text_index sqlite3 /db/hbi.db "PRAGMA integrity_check;"

# Backup verification
ls -la /backups/
```

#### Monthly Tasks
```bash
# Performance benchmarking
# Security updates
# Configuration review
# Capacity planning
```

### Best Practices

1. **Monitor resource usage** proactively
2. **Implement proper logging** and alerting
3. **Regular backups** and testing
4. **Keep dependencies updated**
5. **Document custom configurations**
6. **Test failover scenarios**
7. **Review security policies**

## Getting Help

### Support Resources

1. **Documentation**: Check this troubleshooting guide first
2. **Logs**: Review application and system logs
3. **Metrics**: Check Grafana dashboards
4. **Community**: Search existing issues and solutions
5. **Team**: Contact appropriate team members

### Escalation Process

1. **Level 1**: Check documentation and logs
2. **Level 2**: Review monitoring dashboards
3. **Level 3**: Contact DevOps team
4. **Level 4**: Escalate to system administrators

### Useful Commands Summary

```bash
# Service management
docker-compose ps                    # Check service status
docker-compose logs [service]        # View service logs
docker-compose restart [service]     # Restart service

# Health checks
curl http://localhost:8000/health    # API health
curl http://localhost:8000/config    # Configuration check

# Queue management
docker-compose exec redis redis-cli LLEN arq:queue  # Queue length
docker-compose exec redis redis-cli LLEN dlq:book_processing  # DLQ length

# Database checks
docker-compose exec text_index sqlite3 /db/hbi.db ".tables"  # SQLite tables
docker-compose exec neo4j cypher-shell -u neo4j -p password "MATCH () RETURN count(*);"  # Neo4j check

# Resource monitoring
docker stats                         # Container resources
docker system df                     # Docker disk usage
```

This troubleshooting guide covers the most common issues encountered with the HBI system. For issues not covered here, consult the system logs and consider reaching out to the development team.