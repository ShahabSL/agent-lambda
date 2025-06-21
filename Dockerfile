# Use Python 3.12 Lambda base image
FROM public.ecr.aws/lambda/python:3.12

# Copy Lambda Web Adapter from the official ECR repository
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

# Set environment variables for Lambda Web Adapter
ENV AWS_LWA_ENABLE_COMPRESSION=true
ENV AWS_LWA_ASYNC_INIT=true
ENV PORT=8080

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Set the working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Create a Python wrapper script that starts the web server
RUN echo -e "import subprocess\nimport sys\nsubprocess.run([sys.executable, '-m', 'uvicorn', 'src.main:app', '--host', '0.0.0.0', '--port', '8080'])" > /var/task/start.py

# Override the entrypoint to use our startup script
ENTRYPOINT []
CMD ["python", "start.py"] 