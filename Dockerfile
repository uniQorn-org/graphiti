FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY . /app/

RUN uv pip install --system \
    "mcp[cli]>=1.9.4" \
    "graphiti-core[falkordb]>=0.16.0" \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "python-dotenv>=1.0.1" \
    "pydantic>=2.12.3" \
    "pydantic-settings>=2.0.0" \
    "pandas>=2.3.3" \
    "tqdm>=4.67.1" \
    "openai>=1.91.0" \
    "boto3>=1.28.0" \
    "PyGithub>=2.1.0" \
    "requests>=2.31.0"

EXPOSE 8001

CMD ["python", "src/graphiti_mcp_server.py", "--transport", "http", "--database-provider", "neo4j", "--port", "8001", "--host", "0.0.0.0"]
