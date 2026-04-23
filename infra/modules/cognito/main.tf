terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# ─────────────────────────────────────────────
# Cognito User Pool
#
# Notes:
#   - email is the primary identifier and auto-verified
#   - password policy enforces min 8 chars, upper, lower, number
#     per requirement 6.6 (no special char requirement for MVP usability)
#   - account_recovery_setting: email-only recovery keeps it simple
# ─────────────────────────────────────────────
resource "aws_cognito_user_pool" "this" {
  name = var.user_pool_name

  # Email is the primary sign-in attribute and is auto-verified
  auto_verified_attributes = ["email"]

  username_attributes = ["email"]

  # Password policy per requirement 6.6
  password_policy {
    minimum_length    = 8
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false # Not required for MVP — keeps demo friction low
  }

  # Send verification code via email
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  # Allow users to recover their account via email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = {
    Environment = var.environment
  }
}

# ─────────────────────────────────────────────
# Cognito App Client
#
# Notes:
#   - generate_secret = false: public client for web/mobile apps
#     (SPA and mobile cannot safely store a client secret)
#   - ALLOW_USER_PASSWORD_AUTH: enables username+password flow
#     used by the React dashboard and demo script
#   - ALLOW_REFRESH_TOKEN_AUTH: enables token refresh without
#     re-authentication — required for good UX
# ─────────────────────────────────────────────
resource "aws_cognito_user_pool_client" "this" {
  name         = var.client_name
  user_pool_id = aws_cognito_user_pool.this.id

  # Public client — no secret (web/mobile cannot store secrets securely)
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}
