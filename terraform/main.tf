# --- Provider Configuration ---
# This block tells Terraform that we will be working with the AWS provider.
# We also specify the region where our resources will be created.
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1" # You can change this to your preferred region
}

# --- Resource Naming ---
# A common best practice is to use a variable for a project prefix
# to ensure all created resources have a unique and identifiable name.
variable "project_name" {
  description = "A unique name for the project to prefix resources."
  type        = string
  default     = "stock-agent"
}

# --- ECR (Elastic Container Registry) ---
# We need a repository to store the Docker image of our application.
# AWS ECR is a managed container registry that is secure and scalable.
resource "aws_ecr_repository" "app_repo" {
  name = "${var.project_name}-repo"

  # It's a good security practice to ensure that images are scanned for
  # vulnerabilities upon being pushed to the repository.
  image_scanning_configuration {
    scan_on_push = true
  }

  image_tag_mutability = "MUTABLE"
}

# --- IAM (Identity and Access Management) ---
# This section defines the permissions for our Lambda function. We follow
# the principle of least privilege, only granting the permissions necessary.

# 1. The IAM Role for our Lambda function.
# This creates an "identity" that the Lambda function can assume.
# The "assume_role_policy" specifies WHO can assume this role. In this
# case, it's the AWS Lambda service itself.
resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.project_name}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Action    = "sts:AssumeRole",
      Effect    = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# 2. The IAM Policy.
# This policy defines WHAT the role is allowed to do.
# We are creating a policy that grants permission to create log streams,
# write log events, and invoke the Bedrock model.
resource "aws_iam_policy" "lambda_exec_policy" {
  name        = "${var.project_name}-lambda-exec-policy"
  description = "IAM policy for Lambda to log to CloudWatch and invoke Bedrock."

  policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action   = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action   = "bedrock:InvokeModel",
        Effect   = "Allow",
        # It is best practice to scope this to the specific model ARN if possible,
        # but for this project, a wildcard is acceptable for simplicity.
        Resource = "arn:aws:bedrock:*:*:foundation-model/*"
      }
    ]
  })
}

# 3. Attaching the Policy to the Role.
# This crucial step connects the permissions (the policy) to the
# identity (the role).
resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_exec_policy.arn
}

# --- Lambda Function ---
# This defines the serverless function itself. It pulls together the
# container image from ECR and the permissions from the IAM role.
resource "aws_lambda_function" "app_function" {
  function_name = "${var.project_name}-function"
  role          = aws_iam_role.lambda_exec_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app_repo.repository_url}:latest"
  memory_size   = 1024  # Increased for better performance with LLM calls
  timeout       = 900   # Increased for complex queries and streaming (15 minutes max)

  environment {
    variables = {
      ENV = "PROD"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_policy_attach,
  ]
}

# --- Lambda Function URL ---
# This provides a direct HTTPS endpoint to the Lambda function with streaming support
# and longer timeout limits (15 minutes vs API Gateway's 29 seconds)
resource "aws_lambda_function_url" "app_function_url" {
  function_name      = aws_lambda_function.app_function.function_name
  authorization_type = "NONE"  # We'll handle API key auth in the application

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["date", "keep-alive", "x-api-key", "content-type"]
    expose_headers    = ["date", "keep-alive"]
    max_age          = 86400
  }
}

# --- API Gateway (REST API) ---
# We use REST API Gateway to support API Keys and Usage Plans.

resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-api"
  description = "API for the stock analysis agent"
}

# A REST API needs an explicit "resource" to define a URL path.
# We create a greedy proxy resource that catches all paths.
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

# A "method" defines the HTTP verb (e.g., GET, POST) for a resource.
# We are allowing ANY method to be passed through to our Lambda.
resource "aws_api_gateway_method" "proxy_method" {
  rest_api_id      = aws_api_gateway_rest_api.api.id
  resource_id      = aws_api_gateway_resource.proxy.id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = true # This is the correct way to enforce keys on a REST API
}

# The "integration" connects the method to our Lambda backend.
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_method.http_method
  integration_http_method = "POST" # Lambda proxy integrations must be POST
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.app_function.invoke_arn
}

# A "deployment" is a snapshot of the API that can be deployed to a stage.
resource "aws_api_gateway_deployment" "api_deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  # This trigger ensures that a new deployment is created whenever our API changes.
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy_method.id,
      aws_api_gateway_integration.lambda_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# A "stage" is a named reference to a deployment (e.g., dev, prod, v1).
resource "aws_api_gateway_stage" "api_stage" {
  deployment_id = aws_api_gateway_deployment.api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"
}

# Lambda Permission.
# This grants the API Gateway service permission to invoke our Lambda function.
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app_function.function_name
  principal     = "apigateway.amazonaws.com"

  # The source ARN format is different for REST APIs.
  source_arn = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
} 