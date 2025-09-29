#!/bin/bash

# Shipyard Integration Test Runner
# This script sets up the environment and runs integration tests

set -e

echo "🚀 Starting Shipyard Integration Tests"

# Check if we're in the correct directory
if [[ ! -f "pyproject.toml" ]] || [[ ! -d "app" ]]; then
    echo "❌ Error: Please run this script from the bay package directory"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build Ship image if it doesn't exist
if ! docker image inspect ship:latest &> /dev/null; then
    echo "🏗️  Building Ship image..."
    cd ../ship
    docker build -t ship:latest .
    cd ../bay
    echo "✅ Ship image built successfully"
fi

# Check if shipyard network exists, create if not
if ! docker network inspect shipyard &> /dev/null; then
    echo "🌐 Creating shipyard network..."
    docker network create shipyard
    echo "✅ Network created successfully"
fi

# Clean up any existing test containers
echo "🧹 Cleaning up existing test containers..."
docker ps -a --filter "ancestor=ship:latest" --format "table {{.ID}}" | tail -n +2 | xargs -r docker rm -f

# Run the tests
echo "🧪 Running integration tests..."
python -m pytest tests/integration/ -v -s --tb=short

# Clean up after tests
echo "🧹 Cleaning up test containers..."
docker ps -a --filter "ancestor=ship:latest" --format "table {{.ID}}" | tail -n +2 | xargs -r docker rm -f

echo "✅ Integration tests completed!"
