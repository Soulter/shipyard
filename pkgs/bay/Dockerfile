FROM python:3.11-slim

# Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc \
#     libc6-dev \
#     libffi-dev \
#     bash \
#     && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY run.py ./
COPY requirements.txt ./

# Install Python dependencies
RUN pip install -r requirements.txt --no-cache-dir

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Start the application
CMD ["python", "run.py"]
