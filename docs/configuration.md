# HBI System Configuration Guide

This guide covers the operational live tuning knobs and configuration options available in the Hybrid Book Index (HBI) system.

## Overview

The HBI system provides dynamic configuration capabilities that allow operators to tune RAG (Retrieval-Augmented Generation) pipeline parameters in real-time without requiring code deployment or service restarts.

## Configuration Architecture

### Thread-Safe Configuration Store

The system uses an in-memory configuration store with thread safety:

- **Storage**: In-memory (persists for application lifetime)
- **Thread Safety**: Protected with threading locks
- **Validation**: All parameters validated before application
- **Hot Updates**: Changes take effect immediately

### Configuration Schema

```python
class RAGConfig(BaseModel):
    retrieval_top_k: int = 10          # Chunks to retrieve in hybrid search
    min_chunks: int = 2                # Minimum chunks for retrieval gate
    confidence_threshold: float = 0.7  # Minimum confidence for generation gate
    relevance_threshold: float = 0.5   # Minimum relevance for retrieved chunks
    max_context_length: int = 4000     # Maximum LLM context length
    temperature: float = 0.1           # LLM temperature for generation
    enable_fallback: bool = True       # Enable fallback messages
```

## Configuration API

### GET /config

Retrieve the current RAG configuration.

**Example Request:**
```bash
curl http://localhost:8000/config
```

**Example Response:**
```json
{
  "retrieval_top_k": 10,
  "min_chunks": 2,
  "confidence_threshold": 0.7,
  "relevance_threshold": 0.5,
  "max_context_length": 4000,
  "temperature": 0.1,
  "enable_fallback": true
}
```

### PUT /config

Update configuration parameters dynamically.

**Example Request:**
```bash
curl -X PUT http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{
    "retrieval_top_k": 15,
    "confidence_threshold": 0.8,
    "temperature": 0.2
  }'
```

**Partial Updates Supported**: Only specify parameters you want to change.

## Parameter Reference

### Retrieval Parameters

#### `retrieval_top_k` (integer, default: 10)
- **Range**: 1-100
- **Purpose**: Number of text chunks to retrieve during hybrid search
- **Impact**:
  - Higher values: More comprehensive context, slower queries
  - Lower values: Faster queries, potentially less comprehensive answers
- **Use Cases**:
  - Increase for complex questions requiring broad context
  - Decrease for simple factual questions

#### `min_chunks` (integer, default: 2)
- **Range**: 1-50
- **Purpose**: Minimum chunks required to pass the retrieval gate
- **Impact**:
  - Higher values: Stricter quality control, more fallbacks
  - Lower values: More lenient, potentially lower quality answers
- **Use Cases**:
  - Increase for high-precision requirements
  - Decrease for exploratory or casual queries

#### `relevance_threshold` (float, default: 0.5)
- **Range**: 0.0-1.0
- **Purpose**: Minimum relevance score for retrieved chunks
- **Impact**:
  - Higher values: Only highly relevant chunks included
  - Lower values: More chunks included, potentially with noise
- **Use Cases**:
  - Increase for precision-critical applications
  - Decrease when recall is more important than precision

### Generation Parameters

#### `confidence_threshold` (float, default: 0.7)
- **Range**: 0.0-1.0
- **Purpose**: Minimum confidence score required for answer generation
- **Impact**:
  - Higher values: Fewer but higher-quality answers
  - Lower values: More answers but potentially lower quality
- **Use Cases**:
  - Increase for applications requiring high accuracy
  - Decrease for exploratory or educational use

#### `max_context_length` (integer, default: 4000)
- **Range**: 100-8000
- **Purpose**: Maximum context length sent to LLM
- **Impact**:
  - Higher values: More context, better answers, higher costs
  - Lower values: Less context, faster responses, lower costs
- **Use Cases**:
  - Increase for complex multi-part questions
  - Decrease for simple questions or cost optimization

#### `temperature` (float, default: 0.1)
- **Range**: 0.0-2.0
- **Purpose**: Controls randomness in LLM generation
- **Impact**:
  - Lower values (0.0-0.3): More deterministic, consistent answers
  - Higher values (0.7-1.0): More creative, varied answers
- **Use Cases**:
  - Low temperature: Factual Q&A, technical documentation
  - High temperature: Creative writing, brainstorming

### Fallback Parameters

#### `enable_fallback` (boolean, default: true)
- **Purpose**: Whether to provide fallback messages when quality gates fail
- **Impact**:
  - `true`: User-friendly messages when system cannot answer confidently
  - `false`: No response when quality gates fail (stricter mode)
- **Use Cases**:
  - Keep `true` for user-facing applications
  - Set `false` for automated systems requiring strict quality control

## Quality Gates

The system implements two quality gates that use these configuration parameters:

### Retrieval Gate
- **Condition**: `len(retrieved_chunks) >= config.min_chunks`
- **Action on Failure**: Returns fallback message
- **Purpose**: Ensures sufficient relevant context is available

### Generation Gate
- **Condition**: `answer.confidence_score >= config.confidence_threshold`
- **Action on Failure**: Returns fallback message
- **Purpose**: Ensures high-confidence grounded answers

## Operational Scenarios

### High-Precision Mode
```json
{
  "retrieval_top_k": 20,
  "min_chunks": 5,
  "confidence_threshold": 0.9,
  "relevance_threshold": 0.7,
  "temperature": 0.0
}
```
**Use Case**: Legal research, medical information, technical specifications

### Balanced Mode (Default)
```json
{
  "retrieval_top_k": 10,
  "min_chunks": 2,
  "confidence_threshold": 0.7,
  "relevance_threshold": 0.5,
  "temperature": 0.1
}
```
**Use Case**: General Q&A, educational content, documentation

### High-Throughput Mode
```json
{
  "retrieval_top_k": 5,
  "min_chunks": 1,
  "confidence_threshold": 0.5,
  "max_context_length": 2000,
  "temperature": 0.3
}
```
**Use Case**: Chat interfaces, exploratory search, cost-sensitive applications

## Monitoring Configuration Changes

### Logging
All configuration changes are logged:

```
INFO - RAG configuration updated: {'retrieval_top_k': 15, 'confidence_threshold': 0.8}
```

### Audit Trail
- Changes are logged with timestamps
- Previous values are not stored (in-memory only)
- Configuration persists until service restart

## Configuration Validation

### Parameter Validation Rules

| Parameter | Min | Max | Type | Description |
|-----------|-----|-----|------|-------------|
| `retrieval_top_k` | 1 | 100 | int | Must be positive |
| `min_chunks` | 1 | 50 | int | Must be positive, ≤ `retrieval_top_k` |
| `confidence_threshold` | 0.0 | 1.0 | float | Probability range |
| `relevance_threshold` | 0.0 | 1.0 | float | Probability range |
| `max_context_length` | 100 | 8000 | int | Token limit |
| `temperature` | 0.0 | 2.0 | float | OpenAI range |
| `enable_fallback` | - | - | bool | Boolean flag |

### Validation Errors

**Example Error Response:**
```json
{
  "detail": "retrieval_top_k must be at least 1"
}
```

**Common Validation Errors:**
- `retrieval_top_k must be at least 1`
- `min_chunks cannot be greater than retrieval_top_k`
- `confidence_threshold must be between 0.0 and 1.0`
- `temperature must be between 0.0 and 2.0`

## Configuration Persistence

### In-Memory Storage
- Configuration persists for the application lifetime
- Changes are lost on service restart
- No database persistence (by design for operational flexibility)

### Environment Variables (Future)
For production deployments, consider adding environment variable support:

```bash
RAG_RETRIEVAL_TOP_K=10
RAG_MIN_CHUNKS=2
RAG_CONFIDENCE_THRESHOLD=0.7
```

## Best Practices

### Gradual Tuning
1. Start with default values
2. Monitor system performance and user feedback
3. Make incremental changes (10-20% adjustments)
4. Test changes with representative queries
5. Monitor for quality gate fallback rates

### A/B Testing
Consider implementing A/B testing for configuration changes:
- Route percentage of traffic to new configuration
- Compare answer quality, fallback rates, and user satisfaction
- Gradually roll out successful configurations

### Monitoring Metrics
Track these metrics when tuning configuration:

- **Fallback Rate**: Percentage of queries returning fallback messages
- **Average Confidence**: Mean confidence score of generated answers
- **Query Latency**: Response time percentiles
- **Context Length**: Average context tokens used
- **User Satisfaction**: Feedback scores or thumbs up/down

### Rollback Strategy
- Document baseline configuration before changes
- Have quick rollback procedures
- Monitor error rates and latency after changes
- Be prepared to revert within minutes if issues arise

## Troubleshooting

### Common Issues

#### High Fallback Rate
**Symptoms**: Many queries return fallback messages
**Possible Causes**:
- `min_chunks` too high
- `confidence_threshold` too high
- Poor document quality or relevance
- Index quality issues

**Solutions**:
- Lower `min_chunks` or `confidence_threshold`
- Check document processing quality
- Review index construction

#### Slow Response Times
**Symptoms**: Queries taking too long
**Possible Causes**:
- `retrieval_top_k` too high
- `max_context_length` too high
- Database performance issues

**Solutions**:
- Reduce `retrieval_top_k`
- Lower `max_context_length`
- Optimize database queries

#### Low Answer Quality
**Symptoms**: Answers seem irrelevant or incorrect
**Possible Causes**:
- `relevance_threshold` too low
- `temperature` too high
- Poor chunk quality or embeddings

**Solutions**:
- Increase `relevance_threshold`
- Lower `temperature`
- Review chunking and embedding quality

### Configuration Reset

To reset to default values:

```bash
# This would require a new endpoint or service restart
# Currently, configuration resets on service restart
```

## Future Enhancements

### Planned Features
- **Configuration Profiles**: Predefined configuration sets for different use cases
- **A/B Testing Framework**: Built-in experimentation capabilities
- **Configuration History**: Track configuration changes over time
- **Auto-tuning**: ML-based parameter optimization
- **Configuration Validation**: Test configurations against golden datasets

### Database Persistence
Consider persisting configuration to database for:
- Configuration history and auditing
- Multi-instance synchronization
- Configuration rollback capabilities
- Environment-specific configurations