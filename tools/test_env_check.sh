#!/bin/bash
# Test script for environment variable checking endpoint
# This tests both locally and can be adapted for ECS

set -e

echo "=========================================="
echo "Environment Variable Check Test"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local url=$1
    echo "Testing endpoint: $url"
    echo ""

    # Make request
    response=$(curl -s "$url/api/test/env-check" || echo "ERROR")

    if [ "$response" = "ERROR" ]; then
        echo -e "${RED}✗ Failed to connect to $url${NC}"
        return 1
    fi

    # Pretty print JSON
    echo "$response" | python3 -m json.tool
    echo ""

    # Check if API key is present
    api_key_present=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('openai_api_key_present', False))")

    if [ "$api_key_present" = "True" ]; then
        echo -e "${GREEN}✓ OPENAI_API_KEY is loaded${NC}"
    else
        echo -e "${RED}✗ OPENAI_API_KEY is NOT loaded${NC}"
    fi

    # Check environment type
    env_type=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('environment', 'unknown'))")
    echo -e "Environment type: ${YELLOW}$env_type${NC}"
    echo ""
}

# Parse command line arguments
case "${1:-local}" in
    local)
        echo "Testing LOCAL Docker instance..."
        test_endpoint "http://localhost:8000"
        ;;
    ecs)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide ECS task public IP${NC}"
            echo "Usage: $0 ecs <task-public-ip>"
            exit 1
        fi
        echo "Testing ECS instance at $2..."
        test_endpoint "http://$2:8000"
        ;;
    alb)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide ALB DNS name${NC}"
            echo "Usage: $0 alb <alb-dns-name>"
            exit 1
        fi
        echo "Testing via ALB at $2..."
        test_endpoint "http://$2"
        ;;
    cloudfront)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide CloudFront domain${NC}"
            echo "Usage: $0 cloudfront <cloudfront-domain>"
            exit 1
        fi
        echo "Testing via CloudFront at $2..."
        test_endpoint "https://$2"
        ;;
    *)
        echo "Usage: $0 [local|ecs|alb|cloudfront] [address]"
        echo ""
        echo "Examples:"
        echo "  $0 local                                    # Test local Docker"
        echo "  $0 ecs 54.123.45.67                        # Test ECS task"
        echo "  $0 alb my-alb-123.us-east-1.elb.amazonaws.com"
        echo "  $0 cloudfront d123abc.cloudfront.net"
        exit 1
        ;;
esac

echo "=========================================="
echo "Test completed"
echo "=========================================="
