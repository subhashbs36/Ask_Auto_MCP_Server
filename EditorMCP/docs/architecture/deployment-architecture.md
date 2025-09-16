# Deployment Architecture Documentation

## Overview

The JSON Editor MCP Tool can be deployed in various configurations depending on the use case, from simple single-instance deployments to scalable multi-instance setups with load balancing.

## Deployment Options

### 1. Single Instance Deployment (Development/Testing)

**Architecture:**
```
[MCP Client] → [JSON Editor MCP Server] → [Redis] + [LLM Provider APIs]
```

**Characteristics:**
- Single server instance
- Local or containerized Redis
- Direct LLM provider connections
- Suitable for development, testing, and low-volume production

**Resource Requirements:**
- CPU: 2-4 cores
- Memory: 4-8 GB RAM
- Storage: 10-20 GB (logs, configuration)
- Network: Stable internet for LLM API calls

### 2. High Availability Deployment (Production)

**Architecture:**
```
[Load Balancer] → [Multiple MCP Server Instances] → [Redis Cluster] + [LLM Provider APIs]
                                ↓
                        [Monitoring & Logging]
```

**Characteristics:**
- Multiple server instances behind load balancer
- Redis cluster for session persistence
- Centralized monitoring and logging
- Auto-scaling capabilities

**Resource Requirements:**
- CPU: 4-8 cores per instance
- Memory: 8-16 GB RAM per instance
- Storage: 50-100 GB (distributed)
- Network: High bandwidth, low latency

### 3. Containerized Deployment (Docker/Kubernetes)

**Architecture:**
```
[Ingress Controller] → [MCP Server Pods] → [Redis StatefulSet] + [External LLM APIs]
                              ↓
                    [ConfigMaps & Secrets]
```

**Characteristics:**
- Container orchestration
- Horizontal pod autoscaling
- Configuration via ConfigMaps
- Secret management for API keys

## Infrastructure Components

### Application Layer

#### MCP Server Instances
- **Purpose**: Handle MCP protocol requests and JSON editing operations
- **Scaling**: Horizontal scaling supported (stateless design)
- **Health Checks**: HTTP endpoints for liveness and readiness probes
- **Configuration**: Environment variables or mounted config files

#### Load Balancer (Optional)
- **Purpose**: Distribute requests across multiple server instances
- **Options**: 
  - Cloud load balancers (AWS ALB, GCP Load Balancer)
  - Nginx/HAProxy for on-premises
  - Kubernetes Ingress controllers
- **Features**: Health checks, SSL termination, request routing

### Data Layer

#### Redis Session Store
- **Purpose**: Persistent session storage for preview/apply workflow
- **Deployment Options**:
  - Single Redis instance (development)
  - Redis Sentinel (high availability)
  - Redis Cluster (horizontal scaling)
  - Managed Redis services (AWS ElastiCache, GCP Memorystore)

**Redis Configuration:**
```yaml
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### External Services

#### LLM Provider APIs
- **Gemini API**: Google Cloud AI Platform
- **OpenAI API**: OpenAI platform
- **Custom LLM**: Self-hosted or third-party endpoints

**Network Requirements:**
- Outbound HTTPS (443) to LLM provider endpoints
- API rate limiting considerations
- Retry and circuit breaker patterns

## Configuration Management

### Environment-Based Configuration

**Development Environment:**
```bash
# LLM Configuration
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-pro

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Server Configuration
LOG_LEVEL=DEBUG
MAX_DOCUMENT_SIZE=10485760
```

**Production Environment:**
```bash
# LLM Configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=${SECRET_OPENAI_KEY}
OPENAI_MODEL=gpt-4

# Redis Configuration (Cluster)
REDIS_HOST=redis-cluster.internal
REDIS_PORT=6379
REDIS_PASSWORD=${SECRET_REDIS_PASSWORD}

# Server Configuration
LOG_LEVEL=INFO
MAX_DOCUMENT_SIZE=52428800
MONITORING_ENABLED=true
```

### Configuration Files

**config.yaml Structure:**
```yaml
server:
  host: "0.0.0.0"
  port: 8080
  log_level: "INFO"
  max_document_size: 10485760

llm:
  provider: "gemini"
  model: "gemini-pro"
  timeout: 30
  retry_attempts: 3
  backoff_factor: 2.0

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  connection_pool_size: 10

prompts:
  system_prompt_file: "prompts/system_prompt.txt"
  guardrails_prompt_file: "prompts/guardrails_prompt.txt"

guardrails:
  enabled: true
  max_changes_per_request: 50
  forbidden_patterns: []
  allowed_json_types: ["object", "array", "string", "number", "boolean"]
```

## Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Start application
CMD ["python", "run_server.py"]
```

### Docker Compose (Development)
```yaml
version: '3.8'

services:
  json-editor-mcp:
    build: .
    ports:
      - "8080:8080"
    environment:
      - LLM_PROVIDER=gemini
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - REDIS_HOST=redis
      - LOG_LEVEL=DEBUG
    depends_on:
      - redis
    volumes:
      - ./config:/app/config
      - ./prompts:/app/prompts

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

## Kubernetes Deployment

### Deployment Manifest
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: json-editor-mcp
  labels:
    app: json-editor-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: json-editor-mcp
  template:
    metadata:
      labels:
        app: json-editor-mcp
    spec:
      containers:
      - name: json-editor-mcp
        image: json-editor-mcp:latest
        ports:
        - containerPort: 8080
        env:
        - name: LLM_PROVIDER
          value: "openai"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: openai-api-key
        - name: REDIS_HOST
          value: "redis-service"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        - name: prompts-volume
          mountPath: /app/prompts
      volumes:
      - name: config-volume
        configMap:
          name: json-editor-config
      - name: prompts-volume
        configMap:
          name: json-editor-prompts
```

### Service and Ingress
```yaml
apiVersion: v1
kind: Service
metadata:
  name: json-editor-mcp-service
spec:
  selector:
    app: json-editor-mcp
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: json-editor-mcp-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: json-editor-mcp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: json-editor-mcp-service
            port:
              number: 80
```

## Monitoring and Observability

### Metrics Collection
- **Application Metrics**: Request count, response times, error rates
- **System Metrics**: CPU, memory, disk usage
- **LLM Metrics**: API call latency, rate limiting, error rates
- **Redis Metrics**: Connection count, memory usage, operation latency

### Logging Strategy
```python
# Structured logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/json-editor-mcp.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}
```

### Health Check Endpoints
```python
# Health check implementation
@app.route('/health')
def health_check():
    """Liveness probe endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}

@app.route('/ready')
def readiness_check():
    """Readiness probe endpoint"""
    checks = {
        'redis': check_redis_connection(),
        'llm_service': check_llm_service(),
        'config': check_configuration()
    }
    
    if all(checks.values()):
        return {'status': 'ready', 'checks': checks}
    else:
        return {'status': 'not_ready', 'checks': checks}, 503
```

## Security Considerations

### Network Security
- Use HTTPS/TLS for all external communications
- Implement network policies in Kubernetes
- Restrict outbound connections to required LLM APIs
- Use private networks for Redis connections

### Secret Management
- Store API keys in secure secret stores (Kubernetes Secrets, AWS Secrets Manager)
- Rotate API keys regularly
- Use least-privilege access principles
- Encrypt sensitive configuration data

### Application Security
- Input validation and sanitization
- Rate limiting to prevent abuse
- Request size limits
- Audit logging for security events

## Scaling Considerations

### Horizontal Scaling
- Stateless application design enables easy horizontal scaling
- Session state stored in Redis (shared across instances)
- Load balancer distributes requests evenly
- Auto-scaling based on CPU/memory metrics

### Performance Optimization
- Connection pooling for Redis
- HTTP keep-alive for LLM API calls
- Caching of frequently used prompts
- Async processing where possible

### Capacity Planning
- Monitor request patterns and peak usage
- Plan for LLM API rate limits
- Size Redis appropriately for session storage
- Consider geographic distribution for global usage