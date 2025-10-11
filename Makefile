# =========================================================
# 🎯 VARIABLES
# =========================================================
VENV = env_chatbot_f
PYTHON = $(VENV)/Scripts/python.exe
PIP = $(VENV)/Scripts/pip.exe
REQ_FILE = requirements.txt
DEV_REQ_FILE = requirements-dev.txt
DOCKER_COMPOSE = docker-compose

# =========================================================
# 🛠️ ENVIRONMENT SETUP
# =========================================================
.PHONY: venv
venv: ## 🧱 Create virtual environment and install core dependencies
	python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r $(REQ_FILE)

.PHONY: install-dev
install-dev: venv ## 🧑‍💻 Install development dependencies
	$(PIP) install -r $(DEV_REQ_FILE)
	$(PIP) install -e .[dev]

.PHONY: pre-commit
pre-commit: ## ⚙️ Setup pre-commit hooks
	$(PIP) install pre-commit
	pre-commit install

# =========================================================
# 🚀 DEVELOPMENT COMMANDS
# =========================================================
.PHONY: dev
dev: ## 🧩 Run FastAPI locally (without Docker)
	$(PYTHON) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: docker-dev
docker-dev: ## 🐳 Run full stack with Docker Compose
	$(DOCKER_COMPOSE) up -d
	@echo "✅ API running at http://localhost:8000/docs"
	@echo "🗄️  Postgres at localhost:5432"
	@echo "💾 MinIO console at http://localhost:9001"

.PHONY: docker-stop
docker-stop:
	$(DOCKER_COMPOSE) down

# =========================================================
# 🧪 TESTING & CODE QUALITY
# =========================================================
.PHONY: test
test: ## 🧠 Run all tests with coverage
	$(PYTHON) -m pytest tests/ -v --cov=src/ --cov-report=term-missing

.PHONY: lint
lint: ## 🧹 Run linters (flake8 + black)
	$(PYTHON) -m flake8 src/ tests/
	$(PYTHON) -m black --check src/ tests/

.PHONY: format
format: ## 🪄 Auto-format with Black + isort
	$(PYTHON) -m black src/ tests/
	$(PYTHON) -m isort src/ tests/

.PHONY: type-check
type-check: ## 🔍 Type checking with mypy
	$(PYTHON) -m mypy src/ --ignore-missing-imports --no-warn-unused-ignores

# =========================================================
# 🤖 ML TASKS & BUILD
# =========================================================
.PHONY: train-ml
train-ml: ## 🧠 Train ML model
	$(PYTHON) ml/train.py

.PHONY: build-docker
build-docker: ## 🏗️ Build Docker image
	docker build -t fraud-chatbot-api .

.PHONY: build-package
build-package: ## 📦 Build Python package
	$(PYTHON) setup.py sdist bdist_wheel

# =========================================================
# ☁️ DEPLOYMENT HELPERS (AWS)
# =========================================================
.PHONY: deploy-terraform
deploy-terraform: ## ☁️ Deploy AWS infra via Terraform
	cd infra/terraform && terraform init && terraform apply -auto-approve -var-file=dev.tfvars

.PHONY: deploy-lambda
deploy-lambda: ## 🚀 Package and deploy AWS Lambda
	./infra/scripts/deploy_lambda.sh

# =========================================================
# 🧹 CLEANUP
# =========================================================
.PHONY: clean
clean: ## 🧹 Remove build artifacts and caches
	@if exist build rmdir /s /q build
	@if exist dist rmdir /s /q dist
	@if exist *.egg-info rmdir /s /q *.egg-info
	@if exist htmlcov rmdir /s /q htmlcov
	@if exist $(VENV) rmdir /s /q $(VENV)
	docker system prune -f
