# Phase 1: Use the official Python base image.
# Using a slim image is a best practice as it reduces the final image size.
FROM python:3.12-slim as base

# Phase 2: Set up the environment.
# This ensures a clean and predictable environment inside the container.
FROM base as builder

# Set the working directory inside the container.
WORKDIR /app

# Install system dependencies that might be needed by Python packages.
# This is a good practice to avoid build failures.
RUN apt-get update && apt-get install -y build-essential

# Copy the requirements file first. This is a Docker caching optimization.
# If the requirements file hasn't changed, Docker will use the cached layer
# from a previous build, speeding up the build process significantly.
COPY requirements.txt .

# Install the Python dependencies.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Phase 3: Add the application code.
FROM builder as final

WORKDIR /app

# Copy the installed dependencies from the 'builder' stage.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

# Copy the application source code.
COPY src/ ./src/

# Download and install the AWS Lambda Web Adapter as a Lambda Extension.
# This runs in the same environment as our function but as a separate process.
# We use ADD to download directly from the URL.
# We are using amd64 architecture, which is the standard for most Lambda environments.
ADD https://github.com/awslabs/aws-lambda-web-adapter/releases/latest/download/aws-lambda-adapter-linux-amd64 /opt/extensions/aws-lambda-adapter

# Set environment variables for the Lambda Web Adapter.
# AWS_LAMBDA_EXEC_WRAPPER allows the adapter to start before our code.
ENV AWS_LAMBDA_EXEC_WRAPPER=/opt/extensions/aws-lambda-adapter
# Tell the adapter where our FastAPI app will be running.
ENV PORT=8080

# The command to run our FastAPI application with uvicorn.
# This is what the Lambda Web Adapter will start. It runs on all network interfaces (0.0.0.0)
# on the port we specified.
CMD ["uvicorn", "src.main:api", "--host", "0.0.0.0", "--port", "8080"] 