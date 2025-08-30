# HBI System Performance and Load Testing Report

## Executive Summary

This report documents the performance and load testing conducted on the Hybrid Book Index (HBI) system using Locust load testing tool. Due to infrastructure limitations (Docker not available in the testing environment), the system could not be started for live testing. However, the load testing framework has been fully prepared and configured for future execution.

## Test Setup

### Load Testing Framework
- **Tool**: Locust 2.39.1
- **Test File**: `load_tests/locustfile.py`
- **Host**: http://localhost:8000
- **User Class**: HBIUser with realistic wait times (1-5 seconds between requests)

### Test Scenarios
The load test simulates three primary user behaviors with weighted distribution:

1. **Query Endpoint (70% weight)**: POST /query
   - Uses sample queries from the golden set dataset
   - Tests the main RAG pipeline with hybrid retrieval
   - Includes confidence scoring and quality gates

2. **Table of Contents Endpoint (20% weight)**: GET /books/{id}/toc
   - Tests hierarchical ToC retrieval
   - Simulates navigation through book structure

3. **Upload Endpoint (10% weight)**: POST /books/{id}/upload
   - Tests PDF/DjVu file upload and processing
   - Uses sample PDF file for realistic payload

### Test Data
- **Sample Queries**: 5 questions from `data/golden_set/golden_set.jsonl`
- **Sample File**: `load_tests/sample.pdf` (generated programmatically)
- **Book ID**: Assumes book with ID 1 exists (would need to be created in live test)

## Limitations and Constraints

### Infrastructure Issues
- Docker Desktop not running/available on Windows environment
- Unable to start HBI system containers via `docker-compose up`
- Load test executed against non-responsive host, resulting in connection errors

### Test Environment Notes
- Load testing from same machine as application can skew results
- No distributed load generation (single machine)
- Network latency not representative of production environment

## Expected Performance Characteristics

Based on system architecture analysis, the following performance expectations:

### System Components
- **API Layer**: FastAPI with async processing
- **Storage**: SQLite with FTS5 (lexical) and sqlite-vec (vector)
- **Background Processing**: Redis/arq for file processing jobs
- **Observability**: Langfuse/Phoenix for LLM traces, Grafana stack for metrics

### Anticipated Bottlenecks
1. **LLM Inference**: Most likely bottleneck under high load
2. **Vector Search**: sqlite-vec performance with large datasets
3. **File Processing**: Background job queue saturation
4. **Database Connections**: SQLite concurrent access limits

### Target Metrics (Estimated)
- **Requests Per Second (RPS)**: 10-50 RPS depending on query complexity
- **p95 Latency**: <5 seconds for /query endpoint
- **p99 Latency**: <10 seconds for /query endpoint
- **Error Rate**: <5% under normal load
- **Concurrent Users**: 50-200 before degradation

## Recommendations

### Immediate Actions
1. **Infrastructure Setup**: Ensure Docker environment is available for testing
2. **System Startup**: Verify `docker-compose up` starts all services successfully
3. **Data Preparation**: Create test book with ID 1 and populate with content
4. **Environment Variables**: Configure necessary .env settings

### Load Test Execution Plan
1. Start HBI system: `docker-compose up`
2. Verify health: `curl http://localhost:8000/health`
3. Run Locust: `locust -f load_tests/locustfile.py --host=http://localhost:8000`
4. Access UI: http://localhost:8089
5. Gradually increase users: 1 → 10 → 50 → 100+ concurrent users
6. Monitor Grafana dashboards for system metrics

### Monitoring Points
- **Locust UI**: RPS, response times, failure rates
- **Grafana**: CPU, memory, disk I/O, database connections
- **Application Logs**: Error patterns, background job status
- **Redis**: Queue lengths, job processing rates

### Optimization Opportunities
1. **Caching**: Implement response caching for frequent queries
2. **Connection Pooling**: Optimize database connection management
3. **Async Processing**: Ensure all I/O operations are properly async
4. **Resource Limits**: Configure appropriate memory/CPU limits per container

## Conclusion

The load testing framework is fully prepared and ready for execution once the system can be started. The test scenarios accurately reflect production usage patterns with proper weighting and realistic data. Future testing should focus on identifying the first component to fail under increasing load and implementing optimizations accordingly.

**Next Steps**: Resolve Docker environment issues and execute the prepared load test to obtain actual performance metrics.