# This file defines the output variables from our Terraform configuration.
# Outputs are a convenient way to expose important information about the
# resources that have been created.

output "api_endpoint" {
  description = "The invocation URL for the API Gateway."
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "api_key_value" {
  description = "The value of the created API key."
  value       = aws_api_gateway_api_key.api_key.value
  sensitive   = true # This prevents Terraform from showing the key in logs.
} 