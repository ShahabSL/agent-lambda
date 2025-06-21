# This file defines the API Gateway security resources: the key and usage plan.

# 1. The API Key itself. Terraform will generate a random value.
resource "aws_api_gateway_api_key" "api_key" {
  name = "${var.project_name}-api-key"
}

# 2. The Usage Plan. This is a container for API keys and throttling limits.
resource "aws_api_gateway_usage_plan" "api_usage_plan" {
  name = "${var.project_name}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.api_stage.stage_name
  }
}

# 3. This links the API key to the usage plan.
resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.api_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.api_usage_plan.id
} 