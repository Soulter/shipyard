FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY run.py ./

# Install Python dependencies
RUN uv pip install --system -e .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "run.py"]
