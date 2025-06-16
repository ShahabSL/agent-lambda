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
  # The function name is prefixed for uniqueness.
  function_name = "${var.project_name}-function"
  
  # We reference the IAM role we created above.
  role = aws_iam_role.lambda_exec_role.arn
  
  # We specify that our function is packaged as a container image.
  package_type = "Image"
  
  # This points to the Docker image in our ECR repository.
  # We are using the "latest" tag for simplicity.
  image_uri = "${aws_ecr_repository.app_repo.repository_url}:latest"

  # Setting a higher timeout is important for LLM-based functions,
  # as model inference and agent loops can take time.
  timeout     = 90
  memory_size = 512
}

# --- API Gateway (HTTP API) ---
# We use the newer, cheaper, and faster HTTP API Gateway (V2).

# 1. The API Gateway definition.
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  
  # This makes the API Gateway call our Lambda function.
  target = aws_lambda_function.app_function.invoke_arn
}

# 2. A deployment stage. An API must be deployed to a stage to be callable.
# We enable auto-deploy so changes are reflected automatically.
resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default" # A special name for the default stage
  auto_deploy = true
}

# 3. Lambda Permission.
# This grants the API Gateway service permission to invoke our Lambda function.
# This is a resource-based policy attached to the Lambda function.
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app_function.function_name
  principal     = "apigateway.amazonaws.com"

  # This locks down the permission to only our specific API Gateway.
  source_arn = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
} 