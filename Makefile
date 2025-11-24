.PHONY: help setup start stop restart logs logs-mcp logs-neo4j logs-backend logs-frontend clean clean-data ps health test ingest-github ingest-slack ingest-zoom shell-mcp shell-neo4j build rebuild

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## Display this help message
	@echo "$(BLUE)Graphiti MCP - Makefile Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Environment Setup

setup: ## Initial setup - check .env and prepare environment
	@echo "$(BLUE)Setting up Graphiti MCP...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env file from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(RED)⚠️  Please edit .env and set your OPENAI_API_KEY$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ .env file exists$(NC)"; \
	fi
	@if ! grep -q "your_openai_api_key_here" .env 2>/dev/null; then \
		echo "$(GREEN)✓ OpenAI API key appears to be configured$(NC)"; \
	else \
		echo "$(RED)⚠️  Please edit .env and set your OPENAI_API_KEY$(NC)"; \
		exit 1; \
	fi
	@mkdir -p data/github data/slack data/zoom
	@echo "$(GREEN)✓ Data directories created$(NC)"
	@echo "$(GREEN)✓ Setup complete! Run 'make start' to launch services$(NC)"

##@ Docker Services

start: setup ## Start all Docker services
	@echo "$(BLUE)Starting all services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo ""
	@echo "$(BLUE)Access URLs:$(NC)"
	@echo "  Neo4j Browser:    http://localhost:7474"
	@echo "  Graphiti MCP:     http://localhost:30547"
	@echo "  Backend API:      http://localhost:20001/docs"
	@echo "  Frontend UI:      http://localhost:20002"
	@echo "  MinIO Console:    http://localhost:20735"
	@echo ""
	@echo "$(YELLOW)Waiting for services to be healthy...$(NC)"
	@sleep 5
	@make health

stop: ## Stop all Docker services
	@echo "$(BLUE)Stopping all services...$(NC)"
	docker-compose stop
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: ## Restart all Docker services
	@echo "$(BLUE)Restarting all services...$(NC)"
	docker-compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build
	@echo "$(GREEN)✓ Images built$(NC)"

rebuild: ## Rebuild Docker images without cache
	@echo "$(BLUE)Rebuilding Docker images (no cache)...$(NC)"
	docker-compose build --no-cache
	@echo "$(GREEN)✓ Images rebuilt$(NC)"

##@ Monitoring

ps: ## Show status of all services
	@docker-compose ps

logs: ## Show logs from all services
	docker-compose logs -f

logs-mcp: ## Show logs from Graphiti MCP server
	docker-compose logs -f graphiti-mcp

logs-neo4j: ## Show logs from Neo4j
	docker-compose logs -f neo4j

logs-backend: ## Show logs from backend API
	docker-compose logs -f search-bot-backend

logs-frontend: ## Show logs from frontend
	docker-compose logs -f search-bot-frontend

logs-minio: ## Show logs from MinIO
	docker-compose logs -f minio

health: ## Check health status of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo ""
	@echo "$(YELLOW)Neo4j:$(NC)"
	@docker-compose exec -T neo4j cypher-shell -u neo4j -p password123 "RETURN 'OK' as status" 2>/dev/null && echo "$(GREEN)✓ Neo4j is healthy$(NC)" || echo "$(RED)✗ Neo4j is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Graphiti MCP:$(NC)"
	@curl -s http://localhost:30547/health > /dev/null && echo "$(GREEN)✓ Graphiti MCP is healthy$(NC)" || echo "$(RED)✗ Graphiti MCP is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)Backend API:$(NC)"
	@curl -s http://localhost:20001/health > /dev/null && echo "$(GREEN)✓ Backend API is healthy$(NC)" || echo "$(RED)✗ Backend API is not responding$(NC)"
	@echo ""
	@echo "$(YELLOW)MinIO:$(NC)"
	@curl -s http://localhost:20734/minio/health/live > /dev/null && echo "$(GREEN)✓ MinIO is healthy$(NC)" || echo "$(RED)✗ MinIO is not responding$(NC)"

##@ Data Ingestion

ingest-github: ## Ingest GitHub issues (requires GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO)
	@if [ -z "$(GITHUB_TOKEN)" ]; then \
		echo "$(RED)Error: GITHUB_TOKEN is not set$(NC)"; \
		echo "Usage: make ingest-github GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=owner GITHUB_REPO=repo"; \
		exit 1; \
	fi
	@if [ -z "$(GITHUB_OWNER)" ]; then \
		echo "$(RED)Error: GITHUB_OWNER is not set$(NC)"; \
		echo "Usage: make ingest-github GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=owner GITHUB_REPO=repo"; \
		exit 1; \
	fi
	@if [ -z "$(GITHUB_REPO)" ]; then \
		echo "$(RED)Error: GITHUB_REPO is not set$(NC)"; \
		echo "Usage: make ingest-github GITHUB_TOKEN=ghp_xxx GITHUB_OWNER=owner GITHUB_REPO=repo"; \
		exit 1; \
	fi
	@echo "$(BLUE)Ingesting GitHub issues from $(GITHUB_OWNER)/$(GITHUB_REPO)...$(NC)"
	docker-compose exec -e GITHUB_TOKEN=$(GITHUB_TOKEN) -e GITHUB_OWNER=$(GITHUB_OWNER) -e GITHUB_REPO=$(GITHUB_REPO) graphiti-mcp python src/ingest_github.py
	@echo "$(GREEN)✓ GitHub issues ingested$(NC)"

ingest-slack: ## Ingest Slack messages (requires SLACK_TOKEN, WORKSPACE_ID, CHANNEL_ID)
	@if [ -z "$(SLACK_TOKEN)" ]; then \
		echo "$(RED)Error: SLACK_TOKEN is not set$(NC)"; \
		echo "Usage: make ingest-slack SLACK_TOKEN=xoxc-... WORKSPACE_ID=T... CHANNEL_ID=C... DAYS=7"; \
		exit 1; \
	fi
	@if [ -z "$(WORKSPACE_ID)" ]; then \
		echo "$(RED)Error: WORKSPACE_ID is not set$(NC)"; \
		echo "Usage: make ingest-slack SLACK_TOKEN=xoxc-... WORKSPACE_ID=T... CHANNEL_ID=C... DAYS=7"; \
		exit 1; \
	fi
	@if [ -z "$(CHANNEL_ID)" ]; then \
		echo "$(RED)Error: CHANNEL_ID is not set$(NC)"; \
		echo "Usage: make ingest-slack SLACK_TOKEN=xoxc-... WORKSPACE_ID=T... CHANNEL_ID=C... DAYS=7"; \
		exit 1; \
	fi
	@DAYS=$${DAYS:-7}; \
	echo "$(BLUE)Ingesting Slack messages (last $$DAYS days)...$(NC)"; \
	docker-compose exec -e SLACK_TOKEN=$(SLACK_TOKEN) graphiti-mcp python src/ingest_slack.py --token $(SLACK_TOKEN) --workspace-id $(WORKSPACE_ID) --channel-id $(CHANNEL_ID) --days $$DAYS
	@echo "$(GREEN)✓ Slack messages ingested$(NC)"

ingest-zoom: ## Ingest Zoom transcripts from data/zoom/ directory
	@echo "$(BLUE)Ingesting Zoom transcripts...$(NC)"
	@if [ -z "$$(ls -A data/zoom/*.vtt 2>/dev/null)" ]; then \
		echo "$(RED)Error: No .vtt files found in data/zoom/$(NC)"; \
		echo "Please place Zoom VTT transcript files in data/zoom/ directory"; \
		exit 1; \
	fi
	docker-compose exec graphiti-mcp python src/ingest_zoom.py --zoom-dir data/zoom
	@echo "$(GREEN)✓ Zoom transcripts ingested$(NC)"

##@ Database Operations

shell-neo4j: ## Open Neo4j Cypher shell
	@echo "$(BLUE)Opening Neo4j Cypher shell...$(NC)"
	docker-compose exec neo4j cypher-shell -u neo4j -p password123

shell-mcp: ## Open shell in Graphiti MCP container
	@echo "$(BLUE)Opening shell in Graphiti MCP container...$(NC)"
	docker-compose exec graphiti-mcp /bin/bash

query-episodes: ## Query all episodes in Neo4j
	@echo "$(BLUE)Querying episodes...$(NC)"
	@docker-compose exec -T neo4j cypher-shell -u neo4j -p password123 "MATCH (e:Episodic) RETURN e.name as name, e.source as source, e.created_at as created_at LIMIT 20"

query-entities: ## Query all entities in Neo4j
	@echo "$(BLUE)Querying entities...$(NC)"
	@docker-compose exec -T neo4j cypher-shell -u neo4j -p password123 "MATCH (e:Entity) RETURN e.name as name, labels(e) as labels LIMIT 20"

query-facts: ## Query all facts in Neo4j
	@echo "$(BLUE)Querying facts...$(NC)"
	@docker-compose exec -T neo4j cypher-shell -u neo4j -p password123 "MATCH ()-[r]->() WHERE exists(r.fact) RETURN r.fact as fact, r.created_at as created_at LIMIT 20"

##@ Testing & Development

test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	@if [ -d "tests" ]; then \
		python tests/test_graphiti.py; \
	else \
		echo "$(YELLOW)No tests directory found$(NC)"; \
	fi

search: ## Search the knowledge graph (usage: make search QUERY="your query")
	@if [ -z "$(QUERY)" ]; then \
		echo "$(RED)Error: QUERY is not set$(NC)"; \
		echo "Usage: make search QUERY=\"your search query\""; \
		exit 1; \
	fi
	@echo "$(BLUE)Searching for: $(QUERY)$(NC)"
	@curl -s -X POST http://localhost:30547/graph/search \
		-H "Content-Type: application/json" \
		-d '{"query": "$(QUERY)", "limit": 5}' | python3 -m json.tool

##@ Cleanup

clean: ## Stop and remove all containers
	@echo "$(BLUE)Stopping and removing containers...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Containers removed$(NC)"

clean-data: ## Stop containers and remove all data (WARNING: destructive!)
	@echo "$(RED)WARNING: This will delete all data in Neo4j, MinIO, and local data directories!$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to cancel, or Enter to continue...$(NC)"
	@read confirm
	@echo "$(BLUE)Removing all containers and volumes...$(NC)"
	docker-compose down -v
	@echo "$(BLUE)Cleaning local data directories...$(NC)"
	rm -rf data/github/*.json data/slack/*.json data/zoom/*.vtt
	@echo "$(GREEN)✓ All data cleaned$(NC)"

clean-cache: ## Clean Python cache files
	@echo "$(BLUE)Cleaning Python cache files...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cache cleaned$(NC)"

##@ Quick Commands

quick-start: ## Quick start (setup + start + health check)
	@make setup
	@make start
	@echo ""
	@echo "$(GREEN)✓ Graphiti MCP is ready!$(NC)"
	@echo ""
	@echo "$(BLUE)Next steps:$(NC)"
	@echo "  1. Visit http://localhost:20002 to use the search UI"
	@echo "  2. Visit http://localhost:7474 to explore Neo4j (user: neo4j, password: password123)"
	@echo "  3. Ingest data with 'make ingest-github', 'make ingest-slack', or 'make ingest-zoom'"
	@echo ""
	@echo "$(YELLOW)Need help? Run 'make help'$(NC)"

dev: ## Start services and show logs
	@make start
	@make logs
