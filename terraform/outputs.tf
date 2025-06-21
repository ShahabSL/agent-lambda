# This file defines the output variables from our Terraform configuration.
# Outputs are a convenient way to expose important information about the
# resources that have been created.

output "api_endpoint" {
  description = "The invocation URL for the API Gateway"
  value       = aws_api_gateway_stage.api_stage.invoke_url
}

output "api_key_value" {
  description = "The value of the API key"
  value       = aws_api_gateway_api_key.api_key.value
  sensitive   = true
}

# Lambda Function URL for streaming support
output "function_url" {
  description = "The Lambda Function URL for direct streaming access (15-minute timeout)"
  value       = aws_lambda_function_url.app_function_url.function_url
}

# Legacy API Gateway endpoint (29-second timeout)
output "api_url" {
  description = "The API Gateway URL (legacy, 29-second timeout limit)"
  value       = aws_api_gateway_stage.api_stage.invoke_url
} 