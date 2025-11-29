"""Constants for Graphiti configuration."""

import os

# Episode processing configuration
DEFAULT_EPISODE_DELAY = int(os.getenv("EPISODE_PROCESSING_DELAY", "20"))
MAX_RETRY_COUNT = int(os.getenv("MAX_RETRY_COUNT", "5"))

# LLM temperature settings
DEFAULT_LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
TRANSLATION_TEMPERATURE = float(os.getenv("TRANSLATION_TEMPERATURE", "0.3"))
ASCII_DETECTION_THRESHOLD = float(os.getenv("ASCII_DETECTION_THRESHOLD", "0.7"))

# Text truncation limits (characters)
MAX_CHARS_TITLE = int(os.getenv("MAX_CHARS_TITLE", "500"))
MAX_CHARS_BODY = int(os.getenv("MAX_CHARS_BODY", "5000"))
MAX_CHARS_COMMENT = int(os.getenv("MAX_CHARS_COMMENT", "2000"))
MAX_CHARS_SLACK = int(os.getenv("MAX_CHARS_SLACK", "1000"))
MAX_CHARS_ZOOM = int(os.getenv("MAX_CHARS_ZOOM", "500"))
MAX_CHARS_DEFAULT = int(os.getenv("MAX_CHARS_DEFAULT", "10000"))

# HTTP settings
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT", "120.0"))

# MCP Server configuration
DEFAULT_MCP_URL = os.getenv("MCP_URL", "http://localhost:8001/mcp/")

# MinIO configuration (for Zoom transcripts)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:20734")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", MINIO_ENDPOINT)
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "miniosecret")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "zoom-transcripts")

# Translation model
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "gpt-4o-mini")

# API URLs
SLACK_CONVERSATIONS_API_URL = "https://slack.com/api/conversations.history"
SLACK_USERS_API_URL = "https://slack.com/api/users.info"
SLACK_FETCH_LIMIT = 100

# Search and query limits
DEFAULT_SEARCH_LIMIT = 10
DEFAULT_MAX_FACTS = 5
DEFAULT_MAX_NODES = 100
DEFAULT_MAX_EPISODES = 100

# Ingestion wait times (seconds)
INGESTION_WAIT_SHORT = 60
INGESTION_WAIT_LONG = 70

# Quality score thresholds
QUALITY_SCORE_EXCELLENT = 80
QUALITY_SCORE_GOOD = 60
QUALITY_SCORE_NEEDS_IMPROVEMENT = 40

# Episode length thresholds (characters)
EPISODE_LENGTH_MIN_OPTIMAL = 200
EPISODE_LENGTH_MAX_OPTIMAL = 2000
EPISODE_LENGTH_MIN_ACCEPTABLE = 100

# Node/Episode ratio thresholds
NODE_EPISODE_RATIO_MIN = 0.3
NODE_EPISODE_RATIO_MAX = 3.0

# Fact/Node ratio thresholds
FACT_NODE_RATIO_GOOD = 1.0
FACT_NODE_RATIO_ACCEPTABLE = 0.5

# Entity node ratio threshold
ENTITY_NODE_RATIO_GOOD = 0.8

# Fact type diversity threshold
FACT_TYPE_DIVERSE_MIN = 3

# Timeout values (seconds)
PROXY_TIMEOUT_SECONDS = 60.0
HTTP_CLIENT_TIMEOUT = 60.0
