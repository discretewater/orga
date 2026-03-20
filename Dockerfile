# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if any (none for now)
# RUN apt-get update && apt-get install -y ...

# Copy the current directory contents into the container at /app
COPY . /app

# Install build tools and dependencies
# We use pip to install the package in editable mode or just requirements
# Since we have pyproject.toml, we can install directly
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir "fastapi" "uvicorn"

# Expose ports (documentary only)
EXPOSE 8000
EXPOSE 8001

# Define environment variables
ENV PYTHONUNBUFFERED=1

# Default entrypoint (can be overridden)
CMD ["uvicorn", "examples.extractor_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
