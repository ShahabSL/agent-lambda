# This file contains additional API Gateway configuration for security.

# We need to explicitly create the integration for the Lambda.
# This allows us to modify the route to require an API key.
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.app_function.invoke_arn
}

# We define a default route that sends all traffic to the Lambda integration.
resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "ANY /{proxy+}" # This catches all methods and paths
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"

  # This is the crucial line for security. It enforces the API key requirement.
  api_key_required = true
}

# --- API Key Resources ---

# 1. The Usage Plan. This is a container for API keys and throttling limits.
resource "aws_api_gateway_usage_plan" "api_usage_plan" {
  name = "${var.project_name}-usage-plan"

  api_stages {
    api_id = aws_apigatewayv2_api.http_api.id
    stage  = aws_apigatewayv2_stage.default_stage.name
  }
}

# 2. The API Key itself. Terraform will generate a random value for this.
resource "aws_api_gateway_api_key" "api_key" {
  name = "${var.project_name}-api-key"
}

# 3. The association between the Usage Plan and the API Key.
resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.api_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.api_usage_plan.id
} 