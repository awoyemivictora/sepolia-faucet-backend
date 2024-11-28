# Use the official lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install system dependencies for Python and Web3
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the application files into the container
COPY . /app

# Copy the .env file into the container
COPY .env /app/.env

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
