#!/bin/bash
# Setup AWS Secrets Manager for MyAccessibilityBuddy
# This script creates secrets in AWS Secrets Manager and outputs the ARNs
# for use in ECS task definitions

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "AWS Secrets Manager Setup"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install it from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

echo -e "${GREEN}✓ AWS CLI configured${NC}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# Prompt for secrets
echo "Enter your OpenAI API Key (or press Enter to skip):"
read -s OPENAI_API_KEY
echo ""

echo "Enter your ECB U2A Client ID (or press Enter to skip):"
read CLIENT_ID_U2A
echo ""

echo "Enter your ECB U2A Client Secret (or press Enter to skip):"
read -s CLIENT_SECRET_U2A
echo ""

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if [ -z "$secret_value" ]; then
        echo -e "${YELLOW}Skipping $secret_name (no value provided)${NC}"
        return
    fi

    echo "Creating/updating secret: $secret_name"

    # Try to create the secret
    if aws secretsmanager create-secret \
        --name "$secret_name" \
        --secret-string "$secret_value" \
        --description "MyAccessibilityBuddy - $secret_name" \
        --region "$REGION" 2>/dev/null; then
        echo -e "${GREEN}✓ Created secret: $secret_name${NC}"
    else
        # If creation fails (already exists), update it
        if aws secretsmanager update-secret \
            --secret-id "$secret_name" \
            --secret-string "$secret_value" \
            --region "$REGION" 2>/dev/null; then
            echo -e "${GREEN}✓ Updated secret: $secret_name${NC}"
        else
            echo -e "${RED}✗ Failed to create/update secret: $secret_name${NC}"
            return 1
        fi
    fi

    # Get the ARN
    SECRET_ARN=$(aws secretsmanager describe-secret \
        --secret-id "$secret_name" \
        --region "$REGION" \
        --query ARN \
        --output text)

    echo -e "${GREEN}ARN: $SECRET_ARN${NC}"
    echo ""

    # Store ARN for later use
    eval "${secret_name//-/_}_ARN='$SECRET_ARN'"
}

# Create secrets
create_or_update_secret "myaccessibilitybuddy/openai-api-key" "$OPENAI_API_KEY"
create_or_update_secret "myaccessibilitybuddy/u2a-client-id" "$CLIENT_ID_U2A"
create_or_update_secret "myaccessibilitybuddy/u2a-client-secret" "$CLIENT_SECRET_U2A"

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""

# Generate task definition snippet
echo "Add the following to your ECS task definition:"
echo ""
echo "{"
echo "  \"secrets\": ["

if [ ! -z "$OPENAI_API_KEY" ]; then
    echo "    {"
    echo "      \"name\": \"OPENAI_API_KEY\","
    echo "      \"valueFrom\": \"${myaccessibilitybuddy_openai_api_key_ARN}\""
    echo "    },"
fi

if [ ! -z "$CLIENT_ID_U2A" ]; then
    echo "    {"
    echo "      \"name\": \"CLIENT_ID_U2A\","
    echo "      \"valueFrom\": \"${myaccessibilitybuddy_u2a_client_id_ARN}\""
    echo "    },"
fi

if [ ! -z "$CLIENT_SECRET_U2A" ]; then
    echo "    {"
    echo "      \"name\": \"CLIENT_SECRET_U2A\","
    echo "      \"valueFrom\": \"${myaccessibilitybuddy_u2a_client_secret_ARN}\""
    echo "    }"
fi

echo "  ]"
echo "}"
echo ""

echo "=========================================="
echo "IAM Policy for ECS Task Execution Role"
echo "=========================================="
echo ""
echo "Add this policy to your ECS task execution role:"
echo ""
echo "{"
echo "  \"Version\": \"2012-10-17\","
echo "  \"Statement\": ["
echo "    {"
echo "      \"Effect\": \"Allow\","
echo "      \"Action\": ["
echo "        \"secretsmanager:GetSecretValue\""
echo "      ],"
echo "      \"Resource\": ["

if [ ! -z "$OPENAI_API_KEY" ]; then
    echo "        \"${myaccessibilitybuddy_openai_api_key_ARN}\","
fi

if [ ! -z "$CLIENT_ID_U2A" ]; then
    echo "        \"${myaccessibilitybuddy_u2a_client_id_ARN}\","
fi

if [ ! -z "$CLIENT_SECRET_U2A" ]; then
    echo "        \"${myaccessibilitybuddy_u2a_client_secret_ARN}\""
fi

echo "      ]"
echo "    }"
echo "  ]"
echo "}"
echo ""

echo "=========================================="
echo "Testing Secrets"
echo "=========================================="
echo ""
echo "To verify secrets are accessible:"
echo ""

if [ ! -z "$OPENAI_API_KEY" ]; then
    echo "aws secretsmanager get-secret-value --secret-id myaccessibilitybuddy/openai-api-key --region $REGION"
fi

if [ ! -z "$CLIENT_ID_U2A" ]; then
    echo "aws secretsmanager get-secret-value --secret-id myaccessibilitybuddy/u2a-client-id --region $REGION"
fi

if [ ! -z "$CLIENT_SECRET_U2A" ]; then
    echo "aws secretsmanager get-secret-value --secret-id myaccessibilitybuddy/u2a-client-secret --region $REGION"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
