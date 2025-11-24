# OpenAI API Proxy Configuration

This document explains how to configure Graphiti to use a corporate proxy server for OpenAI API access.

## Overview

When running Graphiti behind a corporate firewall, you may need to configure a proxy server to access OpenAI's API. This configuration applies to:

- **Graphiti MCP Server**: LLM operations and embeddings
- **Translator**: Text translation using OpenAI API
- **Search Bot Backend**: Chat functionality using LangChain

## Configuration

### Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Required: Proxy server URL
OPENAI_PROXY=http://proxy.company.com:8080

# Optional: Proxy authentication (if required)
OPENAI_PROXY_USERNAME=your_username
OPENAI_PROXY_PASSWORD=your_password

# Optional: Comma-separated list of hosts to bypass proxy
NO_PROXY=localhost,127.0.0.1,neo4j,minio,graphiti-mcp
```

### Configuration Examples

#### Basic Proxy (No Authentication)

```bash
OPENAI_PROXY=http://proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1
```

#### Proxy with Authentication

```bash
OPENAI_PROXY=http://proxy.company.com:8080
OPENAI_PROXY_USERNAME=john.doe
OPENAI_PROXY_PASSWORD=your_secure_password
NO_PROXY=localhost,127.0.0.1,neo4j,minio
```

#### HTTPS Proxy

```bash
OPENAI_PROXY=https://secure-proxy.company.com:8443
OPENAI_PROXY_USERNAME=john.doe
OPENAI_PROXY_PASSWORD=your_secure_password
```

## Testing Locally

You can test proxy configuration locally without accessing a corporate network by running a test proxy server.

### Start Test Proxy Server

```bash
# Start mitmproxy (with web UI for inspecting traffic)
docker-compose -f docker-compose.test-proxy.yml up -d

# The proxy will be available at:
# - Proxy: http://localhost:8080
# - Web UI: http://localhost:8081
```

### Configure Environment

```bash
# Set proxy configuration
export OPENAI_PROXY=http://localhost:8080

# Restart your services
docker-compose restart
```

### Inspect Traffic

1. Open http://localhost:8081 in your browser
2. You'll see all HTTP/HTTPS requests going through the proxy
3. Click on any request to inspect headers, body, and response

### Stop Test Proxy

```bash
docker-compose -f docker-compose.test-proxy.yml down
```

## Verification

### Check Logs

When services start, you should see proxy configuration in the logs:

```
✓ OpenAI API proxy configured: proxy.company.com:8080
✓ Proxy authentication enabled
✓ NO_PROXY hosts: localhost,127.0.0.1,neo4j,minio
```

If no proxy is configured:

```
✓ No proxy configured (direct connection)
```

### Test with Translator

```bash
# Test translation through proxy
docker-compose exec graphiti-mcp python -c "
from translator import translate_to_english
result = translate_to_english('こんにちは')
print(f'Translation: {result}')
"
```

### Test with Search Bot

1. Open http://localhost:20002
2. Go to chat tab
3. Send a message
4. Check backend logs for proxy status

## Troubleshooting

### Connection Timeout

**Symptom**: Requests to OpenAI API timeout

**Solution**:
1. Verify proxy URL is correct
2. Check proxy is accessible: `curl -x $OPENAI_PROXY https://api.openai.com`
3. Ensure firewall allows outbound connections to proxy

### Authentication Failed

**Symptom**: 407 Proxy Authentication Required

**Solution**:
1. Verify `OPENAI_PROXY_USERNAME` and `OPENAI_PROXY_PASSWORD` are correct
2. Check if proxy requires domain in username (e.g., `DOMAIN\\username`)
3. Try URL-encoding special characters in password

### SSL Certificate Errors

**Symptom**: SSL certificate verification failed

**Solution**:
1. If using corporate SSL inspection, you may need to add corporate CA certificate
2. For testing only (NOT for production):
   ```bash
   # Disable SSL verification (NOT RECOMMENDED)
   export CURL_CA_BUNDLE=""
   ```

### Internal Services Going Through Proxy

**Symptom**: Connections to Neo4j, MinIO fail when proxy is configured

**Solution**:
Add internal hostnames to `NO_PROXY`:
```bash
NO_PROXY=localhost,127.0.0.1,neo4j,minio,graphiti-mcp,*.internal.company.com
```

### Proxy Not Being Used

**Symptom**: Connections bypass proxy

**Solution**:
1. Check `OPENAI_PROXY` environment variable is set
2. Verify services have been restarted after setting variables
3. Check logs for proxy configuration message
4. Ensure hostname is not in `NO_PROXY` list

## Advanced Configuration

### Different Proxy for Different Services

If you need different proxies for different services, you can set per-service environment variables in `docker-compose.yml`:

```yaml
services:
  graphiti-mcp:
    environment:
      - OPENAI_PROXY=http://proxy1.company.com:8080

  search-bot-backend:
    environment:
      - OPENAI_PROXY=http://proxy2.company.com:8080
```

### Proxy with Custom Timeout

The default timeout is 60 seconds. If you need a longer timeout, modify `utils/proxy_utils.py`:

```python
# In create_httpx_client() and create_async_httpx_client()
http_client = create_httpx_client(timeout=120.0)  # 2 minutes
```

### Using SOCKS Proxy

The current implementation supports HTTP/HTTPS proxies. For SOCKS proxy support, you would need to:

1. Install `httpx[socks]`: Add to `pyproject.toml`
2. Use `socks5://` URL scheme in `OPENAI_PROXY`

## Security Considerations

### Credential Storage

**DO NOT** commit proxy credentials to git. Always use:
- Environment variables
- Secret management systems (AWS Secrets Manager, Azure Key Vault, etc.)
- `.env` file (ensure it's in `.gitignore`)

### Proxy Logs

Be aware that proxy servers may log:
- Request URLs
- Request headers (may include API keys)
- Request/response bodies (may include sensitive data)

Consult your organization's security policy regarding proxy usage.

### NO_PROXY Configuration

Always include internal services in `NO_PROXY`:
```bash
NO_PROXY=localhost,127.0.0.1,*.internal.company.com,neo4j,minio,graphiti-mcp
```

## Production Deployment

### Docker Compose

Ensure environment variables are set in your deployment:

```yaml
services:
  graphiti-mcp:
    environment:
      - OPENAI_PROXY=${OPENAI_PROXY}
      - OPENAI_PROXY_USERNAME=${OPENAI_PROXY_USERNAME}
      - OPENAI_PROXY_PASSWORD=${OPENAI_PROXY_PASSWORD}
      - NO_PROXY=${NO_PROXY}
```

### Kubernetes

Use ConfigMaps for non-sensitive configuration and Secrets for credentials:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: proxy-config
data:
  OPENAI_PROXY: "http://proxy.company.com:8080"
  NO_PROXY: "localhost,127.0.0.1,*.cluster.local"
---
apiVersion: v1
kind: Secret
metadata:
  name: proxy-credentials
type: Opaque
stringData:
  OPENAI_PROXY_USERNAME: "username"
  OPENAI_PROXY_PASSWORD: "password"
```

## Related Files

- [.env.example](../.env.example) - Environment variable template
- [server/src/utils/proxy_utils.py](../server/src/utils/proxy_utils.py) - Proxy utility implementation
- [docker-compose.test-proxy.yml](../docker-compose.test-proxy.yml) - Test proxy server configuration

## Support

If you encounter issues:

1. Check logs for proxy configuration messages
2. Verify proxy is accessible with `curl`
3. Test with local proxy server first
4. Consult your IT department for corporate proxy details
