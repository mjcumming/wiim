FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy only required files first to leverage build cache
COPY wiim/ ./

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir pytest pytest-asyncio pytest-homeassistant-custom-component "homeassistant~=2024.5"

# Default command executes the test-suite
CMD ["pytest", "-q"] 