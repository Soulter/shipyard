.PHONY: install run test clean init-db docker-build docker-run

# Install dependencies
install:
	@echo "📦 Installing dependencies with uv..."
	uv pip install -e .

# Create .env file from template if it doesn't exist
setup:
	@if [ ! -f .env ]; then \
		echo "⚙️  Creating .env file from template..."; \
		cp .env.example .env; \
		echo "⚠️  Please edit .env file to configure your settings"; \
	fi

# Initialize database
init-db:
	@echo "🔧 Initializing database..."
	python scripts/init_db.py

# Run tests
test:
	@echo "🧪 Running tests..."
	python scripts/test_bay.py

# Test Docker integration
test-docker:
	@echo "🐳 Testing Docker integration..."
	python scripts/test_docker.py

# Run the application
run: setup init-db
	@echo "🚀 Starting Bay API server..."
	python run.py

# Clean up generated files
clean:
	@echo "🧹 Cleaning up..."
	rm -f bay.db bay.db-journal
	rm -rf __pycache__ app/__pycache__ app/*/__pycache__
	rm -rf *.egg-info
	rm -rf .pytest_cache

# Format code
format:
	@echo "🎨 Formatting code..."
	black app/ scripts/
	isort app/ scripts/

# Type check
type-check:
	@echo "🔍 Type checking..."
	mypy app/

# Docker build
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t bay-api .

# Docker run
docker-run: docker-build
	@echo "🐳 Running Bay API in Docker..."
	docker-compose up -d

# Stop Docker services
docker-stop:
	@echo "🐳 Stopping Docker services..."
	docker-compose down

# Show logs
logs:
	@echo "📋 Showing logs..."
	docker-compose logs -f bay

# Development setup
dev: install setup init-db
	@echo "🔧 Development environment ready!"
	@echo "💡 Run 'make run' to start the server"
	@echo "💡 Run 'make test' to run tests"
