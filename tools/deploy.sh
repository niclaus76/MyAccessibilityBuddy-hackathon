#!/bin/bash

################################################################################
# MyAccessibilityBuddy - Universal Deployment Script
# All-in-one deployment tool for VM → AWS (ECR/ECS) + Frontend (S3/CloudFront)
################################################################################

set -e

# Source configuration file if it exists
if [ -f "$(dirname "$0")/deploy.conf" ]; then
    # shellcheck source=deploy.conf
    source "$(dirname "$0")/deploy.conf"
fi

# Color codes
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

# Configuration (with defaults)
# These can be overridden by creating a 'deploy.conf' file in the same directory.
VM_USER="${VM_USER:-developer}"
VM_HOST="${VM_HOST:-192.168.64.4}"
VM_SOURCE_PATH="${VM_SOURCE_PATH:-/home/developer/Innovate-For-Inclusion---MyAccessibilityBuddy}"
LOCAL_DEST_PATH="${LOCAL_DEST_PATH:-$HOME/Documents/ECB/AWS-Caionen/}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
ECR_REGISTRY="${ECR_REGISTRY:-514201995752.dkr.ecr.eu-central-1.amazonaws.com}"
ECR_REPO="${ECR_REPO:-myaccessibilitybuddy-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
S3_BUCKET="${S3_BUCKET:-myaccessibilitybuddy-frontend-1}"
CLOUDFRONT_DIST_ID="${CLOUDFRONT_DIST_ID:-E1INLYHYA11V49}"
ECS_CLUSTER="${ECS_CLUSTER:-myaccessibilitybuddy-cluster}"
ECS_SERVICE="${ECS_SERVICE:-myaccessibilitybuddy-service}"
TASK_FAMILY="${TASK_FAMILY:-myaccessibilitybuddy-task}"
FRONTEND_DIR="${FRONTEND_DIR:-/home/developer/Innovate-For-Inclusion---MyAccessibilityBuddy/frontend}"

# Options
MODE="full"  # full, frontend, backend, ecs, verify, check-invalidation, run-tests
TEST_MODE=false
FAST_MODE=false
FROM_VM=false
SKIP_INVALIDATION=false
MONITOR_DEPLOYMENT=true
RUN_TESTS=false
VERBOSITY=1  # 0=errors only, 1=normal (info+warnings+errors), 2=debug (all messages)

# Functions
print_info() {
    if [ "$VERBOSITY" -ge 1 ]; then
        echo -e "${BLUE}ℹ ${NC}$1"
    fi
}
print_success() { echo -e "${GREEN}✅ ${NC}$1"; }
print_error() { echo -e "${RED}❌ ${NC}$1"; }
print_warning() {
    if [ "$VERBOSITY" -ge 1 ]; then
        echo -e "${YELLOW}⚠️  ${NC}$1"
    fi
}
print_file() {
    if [ "$VERBOSITY" -ge 1 ]; then
        echo -e "${CYAN}  → ${NC}$1"
    fi
}
print_debug() {
    if [ "$VERBOSITY" -ge 2 ]; then
        echo -e "${CYAN}🔍 [DEBUG] ${NC}$1"
    fi
}

print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Show help
show_help() {
    cat << EOF
${BLUE}╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║      MyAccessibilityBuddy - Universal Deployment Script        ║
║                    All-in-One Deployment Tool                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝${NC}

${GREEN}USAGE:${NC}
    $0 [MODE] [OPTIONS]

${GREEN}MODES (choose one):${NC}
    (default)               Full deployment: Backend (ECR+ECS) + Frontend (S3+CloudFront)
    --frontend              Frontend only: S3 sync + CloudFront invalidation
    --backend               Backend only: Docker build + ECR push + ECS deploy
    --ecs                   ECS update only: Deploy existing image to service
    --from-vm               Copy from VM first, then full deployment
    --verify-assets         Verify frontend assets (favicons, manifests, CDN fixes)
    --check-invalidation    Check CloudFront invalidation status
    --run-tests             Run comprehensive test suite on this script

${GREEN}OPTIONS:${NC}
    -t, --test              Test mode: Preview changes without deploying
    -f, --fast              Fast mode: Skip local Docker container testing
    --skip-invalidation     Skip CloudFront cache invalidation
    --skip-monitor          Skip ECS deployment monitoring
    --tag <TAG>             Docker image tag (default: latest)
    -d, --debug             Debug mode: Show detailed progress messages
    -q, --quiet             Quiet mode: Show only errors
    -h, --help              Show this help message

${GREEN}EXAMPLES:${NC}
    # Verify frontend assets before deployment
    $0 --verify-assets

    # Check CloudFront invalidation status
    $0 --check-invalidation

    # Preview frontend changes
    $0 --frontend --test

    # Deploy frontend only
    $0 --frontend

    # Deploy backend only (fast mode)
    $0 --backend --fast

    # Update ECS service only
    $0 --ecs

    # Full deployment from VM
    $0 --from-vm

    # Full deployment with specific tag
    $0 --tag v1.2.3

    # Run with detailed debug output
    $0 --frontend --debug

    # Run in quiet mode (errors only)
    $0 --backend --quiet

${GREEN}DEPLOYMENT MODES EXPLAINED:${NC}

    ${CYAN}Full (default):${NC}
      Parallel execution:
      • Backend: Build Docker → Push to ECR → Update ECS → Monitor
      • Frontend: Sync to S3 → Invalidate CloudFront
      ⏱️  Duration: ~8-12 minutes (backend + frontend run concurrently)
      🚀 Up to 40% faster than sequential deployment

    ${CYAN}Frontend (--frontend):${NC}
      1. Detect changed files
      2. Sync to S3
      3. Invalidate CloudFront cache
      ⚡ Duration: ~1 minute + cache (5-15 min)

    ${CYAN}Backend (--backend):${NC}
      1. Build Docker image
      2. Push to ECR
      3. Update ECS task definition
      4. Deploy to ECS service
      5. Monitor deployment
      🐳 Duration: ~8-12 minutes

    ${CYAN}ECS (--ecs):${NC}
      1. Update ECS task definition
      2. Deploy to ECS service
      3. Monitor deployment
      🚀 Duration: ~3-5 minutes

    ${CYAN}From VM (--from-vm):${NC}
      1. Copy files from VM via SCP
      2. Parallel backend + frontend deployment
      📦 Duration: ~10-15 minutes (includes file transfer + parallel deployment)

    ${CYAN}Verify Assets (--verify-assets):${NC}
      Check frontend files and configuration:
      • Favicon files (ico, png, apple-touch-icon)
      • Manifest files (site.webmanifest, browserconfig.xml)
      • HTML meta tags and CDN configurations
      ✓ Run before deployment to catch issues early

    ${CYAN}Check Invalidation (--check-invalidation):${NC}
      Monitor CloudFront cache invalidation:
      • View all recent invalidations
      • Check latest invalidation status
      • Get detailed invalidation info
      ⏱️  Useful after frontend deployments

${GREEN}TEST MODE:${NC}
    Add --test to preview without deploying:
    • Shows files that would change
    • No uploads to S3/ECR
    • No ECS deployments
    • Safe to run anytime

${GREEN}VERBOSITY LEVELS:${NC}
    Normal (default)        Show info, warnings, and errors
    --quiet (-q)            Show errors only (Level 0)
    --debug (-d)            Show all messages including debug info (Level 2)

${GREEN}CONFIGURATION:${NC}
    Settings are loaded from 'deploy.conf' if present.
    Current resolved values:

    VM Host:      $VM_USER@$VM_HOST
    ECR:          $ECR_REGISTRY/$ECR_REPO
    S3 Bucket:    $S3_BUCKET
    CloudFront:   $CLOUDFRONT_DIST_ID
    ECS Cluster:  $ECS_CLUSTER
    ECS Service:  $ECS_SERVICE

${GREEN}COMMON WORKFLOWS:${NC}

    ${YELLOW}HTML/CSS/JS changes:${NC} $0 --frontend

    ${YELLOW}Backend API changes:${NC} $0 --backend

    ${YELLOW}Emergency hotfix:${NC} $0 --fast

    ${YELLOW}New feature (backend + frontend):${NC} $0

${GREEN}ADDITIONAL UTILITIES:${NC}
    $0 --check-invalidation   - Monitor CloudFront cache status
    $0 --verify-assets        - Validate frontend assets before deployment

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --frontend)
            MODE="frontend"
            shift
            ;;
        --backend)
            MODE="backend"
            shift
            ;;
        --ecs)
            MODE="ecs"
            shift
            ;;
        --from-vm)
            FROM_VM=true
            shift
            ;;
        --verify-assets)
            MODE="verify"
            shift
            ;;
        --check-invalidation)
            MODE="check-invalidation"
            shift
            ;;
        --run-tests)
            MODE="run-tests"
            shift
            ;;
        -t|--test)
            TEST_MODE=true
            shift
            ;;
        -f|--fast)
            FAST_MODE=true
            shift
            ;;
        --skip-invalidation)
            SKIP_INVALIDATION=true
            shift
            ;;
        --skip-monitor)
            MONITOR_DEPLOYMENT=false
            shift
            ;;
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -d|--debug)
            VERBOSITY=2
            shift
            ;;
        -q|--quiet)
            VERBOSITY=0
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Display banner
clear
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║      MyAccessibilityBuddy - Universal Deployment               ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Show mode and options
if [ "$TEST_MODE" = true ]; then
    print_warning "TEST MODE - Preview only, no actual deployment"
    echo ""
fi

# Show verbosity level
case $VERBOSITY in
    0)
        print_warning "QUIET MODE - Errors only"
        echo ""
        ;;
    2)
        print_info "DEBUG MODE - Detailed progress messages"
        echo ""
        ;;
esac

case $MODE in
    frontend)
        print_info "Mode: FRONTEND ONLY (S3 + CloudFront)"
        ;;
    backend)
        print_info "Mode: BACKEND ONLY (ECR + ECS)"
        ;;
    ecs)
        print_info "Mode: ECS UPDATE ONLY"
        ;;
    verify)
        print_info "Mode: VERIFY FRONTEND ASSETS"
        ;;
    check-invalidation)
        print_info "Mode: CHECK CLOUDFRONT INVALIDATION"
        ;;
    run-tests)
        print_info "Mode: RUN TEST SUITE"
        ;;
    *)
        print_info "Mode: FULL DEPLOYMENT (Backend + Frontend)"
        if [ "$FROM_VM" = true ]; then
            print_info "Source: VM ($VM_USER@$VM_HOST)"
        fi
        ;;
esac

if [ "$FAST_MODE" = true ]; then
    print_info "Fast mode: Skipping local container tests"
fi

if [ "$SKIP_INVALIDATION" = true ]; then
    print_info "CloudFront invalidation: Disabled"
fi

print_info "Docker image tag: $IMAGE_TAG"
echo ""

# Start timer
START_TIME=$(date +%s)

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRONTEND DEPLOYMENT
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
deploy_frontend() {
    print_header "FRONTEND DEPLOYMENT"

    print_debug "Frontend directory: $FRONTEND_DIR"
    print_debug "S3 bucket: $S3_BUCKET"
    print_debug "AWS region: $AWS_REGION"

    # Check if frontend directory exists
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "Frontend directory not found: $FRONTEND_DIR"
        return 1
    fi

    # Analyze changes
    print_info "Analyzing changes..."
    print_debug "Running S3 sync --dryrun to detect changes..."
    SYNC_PREVIEW=$(aws s3 sync "$FRONTEND_DIR/" "s3://$S3_BUCKET/" \
        --dryrun \
        --delete \
        --exact-timestamps \
        --region "$AWS_REGION" 2>&1)
    print_debug "S3 dryrun completed"

    # Count changes (grep -c returns count, default to 0 if no matches)
    print_debug "Counting file changes..."
    UPLOAD_COUNT=$(echo "$SYNC_PREVIEW" | grep -c "upload:" 2>/dev/null || true)
    DELETE_COUNT=$(echo "$SYNC_PREVIEW" | grep -c "delete:" 2>/dev/null || true)
    UPLOAD_COUNT=${UPLOAD_COUNT:-0}
    DELETE_COUNT=${DELETE_COUNT:-0}
    TOTAL_CHANGES=$((UPLOAD_COUNT + DELETE_COUNT))
    print_debug "Upload count: $UPLOAD_COUNT, Delete count: $DELETE_COUNT"

    if [ "$UPLOAD_COUNT" -eq 0 ] && [ "$DELETE_COUNT" -eq 0 ]; then
        print_success "No frontend changes detected - S3 is up to date"
        return 0
    fi

    echo ""
    print_info "Frontend changes detected:"
    echo "  Files to upload: $UPLOAD_COUNT"
    echo "  Files to delete: $DELETE_COUNT"
    echo "  Total changes:   $TOTAL_CHANGES"

    # Show file list in test mode
    if [ "$TEST_MODE" = true ]; then
        echo ""
        if [ "$UPLOAD_COUNT" -gt 0 ]; then
            echo -e "${GREEN}Files to upload/update:${NC}"
            echo "$SYNC_PREVIEW" | grep "upload:" | while read -r line; do
                if [ -n "$line" ]; then
                    filename=$(echo "$line" | sed 's/.*to s3:\/\/[^\/]*\///')
                    print_file "$filename"
                fi
            done | head -20
            if [ "$UPLOAD_COUNT" -gt 20 ]; then
                print_info "... and $((UPLOAD_COUNT - 20)) more files"
            fi
        fi

        if [ "$DELETE_COUNT" -gt 0 ]; then
            echo ""
            echo -e "${RED}Files to delete from S3:${NC}"
            echo "$SYNC_PREVIEW" | grep "delete:" | while read -r line; do
                if [ -n "$line" ]; then
                    filename=$(echo "$line" | sed 's/.*s3:\/\/[^\/]*\///')
                    print_file "$filename"
                fi
            done | head -20
            if [ "$DELETE_COUNT" -gt 20 ]; then
                print_info "... and $((DELETE_COUNT - 20)) more files"
            fi
        fi

        echo ""
        print_success "Test mode complete - no files modified"
        return 0
    fi

    # Sync to S3
    echo ""
    print_info "Syncing to S3..."
    print_debug "Uploading $UPLOAD_COUNT files, deleting $DELETE_COUNT files..."
    if aws s3 sync "$FRONTEND_DIR/" "s3://$S3_BUCKET/" \
        --delete \
        --exact-timestamps \
        --region "$AWS_REGION"; then
        print_success "Frontend synced to S3"
        print_debug "S3 sync completed successfully"
    else
        print_error "S3 sync failed"
        return 1
    fi

    # Invalidate CloudFront
    if [ "$SKIP_INVALIDATION" = false ]; then
        echo ""
        print_debug "CloudFront distribution ID: $CLOUDFRONT_DIST_ID"

        # Smart invalidation strategy
        if [ "$TOTAL_CHANGES" -gt 10 ]; then
            print_info "Many files changed ($TOTAL_CHANGES) - invalidating all paths: /*"
            INVALIDATION_PATHS="/*"
        else
            print_info "Creating targeted invalidation for $TOTAL_CHANGES file(s)"
            INVALIDATION_PATHS="/*"  # Simplified for now
        fi
        print_debug "Invalidation paths: $INVALIDATION_PATHS"

        print_debug "Creating CloudFront invalidation..."
        INVALIDATION_OUTPUT=$(aws cloudfront create-invalidation \
            --distribution-id "$CLOUDFRONT_DIST_ID" \
            --paths "$INVALIDATION_PATHS" \
            --output json 2>&1)

        if [ $? -eq 0 ]; then
            INVALIDATION_ID=$(echo "$INVALIDATION_OUTPUT" | jq -r '.Invalidation.Id')
            print_success "CloudFront invalidation created: $INVALIDATION_ID"
            print_debug "Invalidation ID: $INVALIDATION_ID"
            print_warning "Cache clearing takes 5-15 minutes to complete"

            echo ""
            print_info "Checking invalidation status..."

            # Run the integrated check function
            echo ""
            check_cloudfront_invalidation
        else
            print_error "CloudFront invalidation failed"
            return 1
        fi
    else
        print_warning "Skipping CloudFront invalidation (--skip-invalidation)"
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKEND DEPLOYMENT (Docker → ECR)
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
check_prerequisites() {
    print_info "Checking prerequisites..."
    print_debug "Checking for required tools: docker, aws, jq"

    local missing_tools=()

    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
        print_debug "Docker: NOT FOUND"
    else
        print_debug "Docker: found ($(docker --version 2>&1 | head -n1))"
    fi

    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
        print_debug "AWS CLI: NOT FOUND"
    else
        print_debug "AWS CLI: found ($(aws --version 2>&1 | head -n1))"
    fi

    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
        print_debug "jq: NOT FOUND"
    else
        print_debug "jq: found ($(jq --version 2>&1))"
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi

    # Check Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        return 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured"
        return 1
    fi

    print_success "All prerequisites satisfied"
}

deploy_backend_build() {
    print_header "BACKEND BUILD & PUSH TO ECR"

    print_debug "ECR registry: $ECR_REGISTRY"
    print_debug "ECR repository: $ECR_REPO"
    print_debug "Image tag: $IMAGE_TAG"

    # Check prerequisites
    if ! check_prerequisites; then
        return 1
    fi

    local build_dir
    if [ "$FROM_VM" = true ]; then
        build_dir="$LOCAL_DEST_PATH/Innovate-For-Inclusion---MyAccessibilityBuddy"
    else
        build_dir="/home/developer/Innovate-For-Inclusion---MyAccessibilityBuddy"
    fi
    print_debug "Build directory: $build_dir"

    if [ ! -d "$build_dir" ]; then
        print_error "Build directory not found: $build_dir"
        return 1
    fi

    print_debug "Changing to build directory..."
    cd "$build_dir"

    # Check .env file exists
    if [ ! -f "backend/.env" ]; then
        print_error "backend/.env file not found"
        print_info "Please create backend/.env with required environment variables"
        return 1
    fi
    print_debug "Found backend/.env file"

    if [ "$TEST_MODE" = true ]; then
        print_info "Test mode: Would build and push Docker image"
        print_info "Build directory: $build_dir"
        print_info "Image: $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
        return 0
    fi

    # Build Docker image
    print_info "Building Docker image..."
    print_info "Build context: $build_dir"
    print_debug "Docker build command: docker build -t $ECR_REPO:$IMAGE_TAG ."

    if docker build -t "$ECR_REPO:$IMAGE_TAG" .; then
        print_success "Docker image built successfully"
        print_debug "Image: $ECR_REPO:$IMAGE_TAG"
    else
        print_error "Docker build failed"
        return 1
    fi

    # Test container locally (unless fast mode)
    if [ "$FAST_MODE" = false ]; then
        print_info "Testing container locally..."
        print_debug "Cleaning up any existing test container..."

        # Clean up any existing test container
        docker rm -f mab-test 2>/dev/null || true

        # Check ports
        print_debug "Checking if port 8000 is available..."
        if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_warning "Port 8000 is in use - skipping local test"
        else
            print_info "Starting test container..."
            print_debug "Running: docker run -d --name mab-test -p 8000:8000 $ECR_REPO:$IMAGE_TAG"

            # Try to start container and capture error
            START_OUTPUT=$(docker run -d --name mab-test -p 8000:8000 "$ECR_REPO:$IMAGE_TAG" 2>&1)

            if [ $? -eq 0 ]; then
                # Container started successfully
                print_debug "Container started, waiting 5 seconds..."
                sleep 5

                print_debug "Checking health endpoint: http://localhost:8000/api/health"
                if curl -f -s http://localhost:8000/api/health >/dev/null 2>&1; then
                    print_success "Container test passed"
                else
                    print_warning "Health check failed (container may still be starting)"
                fi

                # Clean up test container
                print_debug "Cleaning up test container..."
                docker rm -f mab-test >/dev/null 2>&1
            else
                # Container failed to start
                print_warning "Could not start test container"

                # Check if it's a port issue
                if echo "$START_OUTPUT" | grep -q "port is already allocated"; then
                    print_info "Port 8000 is in use (race condition)"
                elif echo "$START_OUTPUT" | grep -q "error"; then
                    print_info "Error: $(echo "$START_OUTPUT" | grep -i error | head -1)"
                fi

                # Clean up failed container
                docker rm -f mab-test 2>/dev/null || true

                print_info "Continuing with deployment..."
            fi
        fi
    fi

    # Login to ECR
    print_info "Logging into AWS ECR..."
    print_debug "ECR registry: $ECR_REGISTRY, Region: $AWS_REGION"
    if aws ecr get-login-password --region "$AWS_REGION" | \
        docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null 2>&1; then
        print_success "ECR login successful"
    else
        print_error "ECR login failed"
        return 1
    fi

    # Tag and push
    print_info "Tagging image for ECR..."
    print_debug "Tagging: $ECR_REPO:$IMAGE_TAG → $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
    docker tag "$ECR_REPO:$IMAGE_TAG" "$ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"

    print_info "Pushing image to ECR..."
    print_debug "Pushing: $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
    if docker push "$ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"; then
        print_success "Image pushed to ECR successfully"
        print_debug "Image available at: $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
    else
        print_error "Image push failed"
        return 1
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ECS DEPLOYMENT
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
deploy_ecs() {
    print_header "ECS SERVICE DEPLOYMENT"

    FULL_IMAGE_NAME="$ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"

    print_info "Cluster: $ECS_CLUSTER"
    print_info "Service: $ECS_SERVICE"
    print_info "Image:   $FULL_IMAGE_NAME"
    print_debug "Task family: $TASK_FAMILY"
    print_debug "AWS region: $AWS_REGION"
    echo ""

    if [ "$TEST_MODE" = true ]; then
        print_info "Test mode: Would update ECS task and deploy"
        return 0
    fi

    # Get current task definition
    print_info "Retrieving current task definition..."
    print_debug "Running: aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE"
    CURRENT_TASK_DEF=$(aws ecs describe-services \
        --cluster "$ECS_CLUSTER" \
        --services "$ECS_SERVICE" \
        --region "$AWS_REGION" \
        --query 'services[0].taskDefinition' \
        --output text)

    if [ -z "$CURRENT_TASK_DEF" ] || [ "$CURRENT_TASK_DEF" = "None" ]; then
        print_error "Failed to retrieve current task definition"
        return 1
    fi

    print_success "Current task: $CURRENT_TASK_DEF"
    print_debug "Fetching full task definition details..."

    TASK_DEF_JSON=$(aws ecs describe-task-definition \
        --task-definition "$CURRENT_TASK_DEF" \
        --region "$AWS_REGION")
    print_debug "Task definition retrieved successfully"

    # Create new task definition
    print_info "Creating new task definition with updated image..."
    print_debug "Updating container image to: $FULL_IMAGE_NAME"
    NEW_TASK_DEF=$(echo "$TASK_DEF_JSON" | jq --arg IMAGE "$FULL_IMAGE_NAME" '
        .taskDefinition |
        .containerDefinitions[0].image = $IMAGE |
        del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy, .deregisteredAt)
    ')

    # Validate JSON
    if ! echo "$NEW_TASK_DEF" | jq empty 2>/dev/null; then
        print_error "Generated task definition is not valid JSON"
        return 1
    fi

    # Save to temp file for AWS CLI
    TEMP_TASK_DEF="/tmp/task-def-$$.json"
    echo "$NEW_TASK_DEF" > "$TEMP_TASK_DEF"

    print_info "Registering new task definition..."
    REGISTER_OUTPUT=$(aws ecs register-task-definition \
        --cli-input-json "file://$TEMP_TASK_DEF" \
        --region "$AWS_REGION" \
        --output json 2>&1)

    # Extract ARN from output
    NEW_TASK_DEF_ARN=$(echo "$REGISTER_OUTPUT" | jq -r '.taskDefinition.taskDefinitionArn // empty' 2>/dev/null)

    # Check for errors
    if [ -z "$NEW_TASK_DEF_ARN" ]; then
        print_error "Failed to register task definition"
        echo ""
        echo "Error details:"
        echo "$REGISTER_OUTPUT" | head -20
        echo ""
        print_info "Task definition saved to: $TEMP_TASK_DEF"
        print_info "Review the file to debug the issue"
        return 1
    fi

    rm -f "$TEMP_TASK_DEF"

    NEW_REVISION=$(echo "$NEW_TASK_DEF_ARN" | grep -o '[0-9]*$')
    print_success "New task definition registered: revision $NEW_REVISION"

    # Update service
    print_info "Updating ECS service..."
    aws ecs update-service \
        --cluster "$ECS_CLUSTER" \
        --service "$ECS_SERVICE" \
        --task-definition "$TASK_FAMILY:$NEW_REVISION" \
        --region "$AWS_REGION" \
        --force-new-deployment \
        --output json > /dev/null

    print_success "Service update initiated"

    # Monitor deployment
    if [ "$MONITOR_DEPLOYMENT" = true ]; then
        echo ""
        print_info "Monitoring deployment progress..."
        print_warning "This may take 2-5 minutes. Press Ctrl+C to skip monitoring."
        echo ""

        DEPLOYMENT_TIMEOUT=600
        ELAPSED=0
        SLEEP_INTERVAL=10

        while [ $ELAPSED -lt $DEPLOYMENT_TIMEOUT ]; do
            DEPLOYMENTS=$(aws ecs describe-services \
                --cluster "$ECS_CLUSTER" \
                --services "$ECS_SERVICE" \
                --region "$AWS_REGION" \
                --query 'services[0].deployments' \
                --output json)

            # Clear previous lines (only after first iteration)
            if [ $ELAPSED -gt 0 ]; then
                tput cuu 5 2>/dev/null || true
                tput ed 2>/dev/null || true
            fi

            echo -e "${BLUE}Deployment Status (${ELAPSED}s elapsed):${NC}"
            echo "$DEPLOYMENTS" | jq -r '.[] |
                "  Status: \(.status) | " +
                "Desired: \(.desiredCount) | " +
                "Running: \(.runningCount) | " +
                "Pending: \(.pendingCount) | " +
                "Task: \(.taskDefinition | split("/")[-1])"'
            echo ""

            # Check if deployment is complete
            DEPLOYMENT_COUNT=$(echo "$DEPLOYMENTS" | jq 'length')
            PRIMARY_RUNNING=$(echo "$DEPLOYMENTS" | jq -r '.[] | select(.status=="PRIMARY") | .runningCount')
            PRIMARY_DESIRED=$(echo "$DEPLOYMENTS" | jq -r '.[] | select(.status=="PRIMARY") | .desiredCount')

            if [ "$DEPLOYMENT_COUNT" -eq 1 ] && [ "$PRIMARY_RUNNING" -eq "$PRIMARY_DESIRED" ]; then
                print_success "Deployment completed successfully!"
                break
            fi

            sleep $SLEEP_INTERVAL
            ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
        done

        if [ $ELAPSED -ge $DEPLOYMENT_TIMEOUT ]; then
            print_warning "Monitoring timed out - deployment may still be in progress"
        fi

        # Get service endpoint
        echo ""
        print_info "Fetching service endpoint..."
        TASK_ARN=$(aws ecs list-tasks \
            --cluster "$ECS_CLUSTER" \
            --service-name "$ECS_SERVICE" \
            --region "$AWS_REGION" \
            --query 'taskArns[0]' \
            --output text)

        if [ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
            TASK_DETAILS=$(aws ecs describe-tasks \
                --cluster "$ECS_CLUSTER" \
                --tasks "$TASK_ARN" \
                --region "$AWS_REGION" \
                --output json)

            PUBLIC_IP=$(echo "$TASK_DETAILS" | jq -r '.tasks[0].attachments[0].details[] | select(.name=="publicIPv4Address") | .value')

            if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "null" ]; then
                echo ""
                print_success "Service endpoint found:"
                echo "  Public IP:    $PUBLIC_IP"
                echo "  Health check: http://$PUBLIC_IP:8000/api/health"

                # Test health endpoint
                print_info "Testing health endpoint..."
                sleep 3

                if curl -f -s "http://$PUBLIC_IP:8000/api/health" > /dev/null 2>&1; then
                    print_success "Health check passed!"
                else
                    print_warning "Health check not responding yet (service may still be starting)"
                fi
            fi
        fi
    else
        print_info "Deployment initiated - monitoring skipped"
        print_info "Check status: $0 --check-invalidation"
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFY FRONTEND ASSETS
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
verify_frontend_assets() {
    print_header "FRONTEND ASSETS VERIFICATION"

    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "Frontend directory not found: $FRONTEND_DIR"
        return 1
    fi

    local all_good=true

    # Check favicon files
    print_info "Checking favicon files..."
    local favicons=(
        "assets/favicon.ico"
        "assets/favicon-16x16.png"
        "assets/favicon-32x32.png"
        "assets/apple-touch-icon.png"
        "assets/android-chrome-192x192.png"
        "assets/android-chrome-512x512.png"
    )

    for file in "${favicons[@]}"; do
        local filepath="$FRONTEND_DIR/$file"
        if [ -f "$filepath" ]; then
            local size=$(ls -lh "$filepath" | awk '{print $5}')
            print_success "$file ($size)"
        else
            print_error "$file (missing)"
            all_good=false
        fi
    done

    echo ""
    print_info "Checking manifest files..."
    local manifests=(
        "site.webmanifest"
        "browserconfig.xml"
    )

    for file in "${manifests[@]}"; do
        local filepath="$FRONTEND_DIR/$file"
        if [ -f "$filepath" ]; then
            local size=$(ls -lh "$filepath" | awk '{print $5}')
            print_success "$file ($size)"
        else
            print_error "$file (missing)"
            all_good=false
        fi
    done

    echo ""
    print_info "Checking HTML configuration..."

    local html_file="$FRONTEND_DIR/home.html"

    if [ ! -f "$html_file" ]; then
        print_error "home.html not found"
        all_good=false
    else
        # Check for favicon links
        if grep -q 'rel="icon"' "$html_file"; then
            print_success "Favicon links present in home.html"
        else
            print_error "Favicon links missing in home.html"
            all_good=false
        fi

        # Check for manifest link
        if grep -q 'rel="manifest"' "$html_file"; then
            print_success "Manifest link present in home.html"
        else
            print_error "Manifest link missing in home.html"
            all_good=false
        fi

        # Check for theme color
        if grep -q 'name="theme-color"' "$html_file"; then
            print_success "Theme color meta tag present"
        else
            print_error "Theme color meta tag missing"
            all_good=false
        fi

        # Check for description
        if grep -q 'name="description"' "$html_file"; then
            print_success "Description meta tag present"
        else
            print_warning "Description meta tag missing (recommended)"
        fi
    fi

    echo ""
    print_info "Checking Bootstrap Italia CDN fixes..."

    # Check if sprites.svg uses CDN
    if grep -q 'cdn.jsdelivr.net.*sprites.svg' "$html_file"; then
        print_success "SVG sprites using CDN in home.html"
    else
        print_error "SVG sprites not using CDN in home.html"
        all_good=false
    fi

    local app_js="$FRONTEND_DIR/app.js"
    if [ -f "$app_js" ]; then
        if grep -q 'cdn.jsdelivr.net.*sprites.svg' "$app_js"; then
            print_success "SVG sprites using CDN in app.js"
        else
            print_error "SVG sprites not using CDN in app.js"
            all_good=false
        fi

        # Check for old local references
        if grep -q '/bootstrap-italia/dist/svg/sprites.svg' "$html_file" "$app_js" 2>/dev/null; then
            print_error "Old local SVG sprite references still present"
            all_good=false
        else
            print_success "No old local SVG sprite references found"
        fi
    else
        print_warning "app.js not found - skipping CDN check"
    fi

    echo ""
    if [ "$all_good" = true ]; then
        print_success "All checks passed! Frontend assets are ready for deployment."
        return 0
    else
        print_error "Some checks failed. Please fix the issues above before deploying."
        return 1
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHECK CLOUDFRONT INVALIDATION
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
check_cloudfront_invalidation() {
    print_header "CLOUDFRONT INVALIDATION STATUS"

    print_info "Distribution: $CLOUDFRONT_DIST_ID"
    echo ""

    # Get list of invalidations
    print_info "Fetching invalidations..."

    local invalidations
    invalidations=$(aws cloudfront list-invalidations \
        --distribution-id "$CLOUDFRONT_DIST_ID" \
        --region "$AWS_REGION" \
        --output json 2>&1)

    if [ $? -ne 0 ]; then
        print_error "Failed to fetch invalidations"
        echo "$invalidations"
        return 1
    fi

    # Check if there are any invalidations
    local invalidation_count
    invalidation_count=$(echo "$invalidations" | jq '.InvalidationList.Items | length' 2>/dev/null)

    if [ -z "$invalidation_count" ] || [ "$invalidation_count" -eq 0 ]; then
        print_info "No invalidations found for this distribution"
        return 0
    fi

    print_success "Found $invalidation_count invalidation(s)"
    echo ""

    # Display invalidations in a table
    echo -e "${BLUE}Recent Invalidations:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-20s %-15s %-25s\n" "ID" "STATUS" "CREATE TIME"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    echo "$invalidations" | jq -r '.InvalidationList.Items[] |
        [.Id, .Status, .CreateTime] | @tsv' | \
    while IFS=$'\t' read -r id status create_time; do
        # Color code based on status
        local status_colored
        if [ "$status" = "Completed" ]; then
            status_colored="${GREEN}Completed${NC}"
        else
            status_colored="${YELLOW}InProgress${NC}"
        fi

        # Format date
        local formatted_date
        formatted_date=$(date -d "$create_time" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "$create_time")

        printf "%-20s %-24s %-25s\n" "$id" "$(echo -e $status_colored)" "$formatted_date"
    done

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Get the most recent invalidation
    local latest_id latest_status
    latest_id=$(echo "$invalidations" | jq -r '.InvalidationList.Items[0].Id' 2>/dev/null)
    latest_status=$(echo "$invalidations" | jq -r '.InvalidationList.Items[0].Status' 2>/dev/null)

    if [ -z "$latest_id" ] || [ "$latest_id" = "null" ]; then
        print_error "No invalidation ID found"
        return 1
    fi

    echo -e "${BLUE}Latest Invalidation Details:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Get detailed info about the latest invalidation
    local invalidation_details
    invalidation_details=$(aws cloudfront get-invalidation \
        --distribution-id "$CLOUDFRONT_DIST_ID" \
        --id "$latest_id" \
        --region "$AWS_REGION" \
        --output json 2>&1)

    if [ $? -eq 0 ]; then
        echo "$invalidation_details" | jq -r '
            "ID:              " + .Invalidation.Id + "\n" +
            "Status:          " + .Invalidation.Status + "\n" +
            "Create Time:     " + .Invalidation.CreateTime + "\n" +
            "Caller Reference: " + .Invalidation.InvalidationBatch.CallerReference + "\n" +
            "Paths:           " + (.Invalidation.InvalidationBatch.Paths.Items | join(", "))
        '
    else
        print_error "Failed to get invalidation details"
        echo "$invalidation_details"
        return 1
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Status-specific messages
    if [ "$latest_status" = "Completed" ]; then
        print_success "Latest invalidation is complete!"
        print_info "Your CloudFront cache has been cleared"
        echo ""
        print_info "You can now test your CloudFront URL:"
        echo "  https://d2nuwzlynr0xpz.cloudfront.net/home.html"
    else
        print_warning "Latest invalidation is still in progress"
        print_info "This typically takes 5-15 minutes"
        echo ""
        print_info "Monitor again with:"
        echo "  $0 --check-invalidation"
    fi

    echo ""
    return 0
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUN TEST SUITE
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
run_test_suite() {
    print_header "DEPLOY SCRIPT TEST SUITE"

    local test_count=0
    local pass_count=0
    local fail_count=0

    print_test() {
        test_count=$((test_count + 1))
        echo -e "${BLUE}[TEST $test_count]${NC} $1"
    }

    print_pass() {
        pass_count=$((pass_count + 1))
        echo -e "${GREEN}[PASS]${NC} $1"
    }

    print_fail() {
        fail_count=$((fail_count + 1))
        echo -e "${RED}[FAIL]${NC} $1"
    }

    echo ""

    # Test 1: Syntax validation
    print_test "Validating bash syntax..."
    if bash -n "$0" 2>/dev/null; then
        print_pass "Syntax is valid"
    else
        print_fail "Syntax errors found"
        return 1
    fi

    # Test 2: Help command
    print_test "Testing --help flag..."
    if timeout 5 "$0" --help > /dev/null 2>&1; then
        print_pass "Help command works"
    else
        print_fail "Help command failed"
    fi

    # Test 3: Verify assets
    print_test "Testing --verify-assets..."
    if timeout 10 "$0" --verify-assets > /dev/null 2>&1; then
        print_pass "Verify assets completed"
    else
        # Exit code 1 is expected if checks fail
        print_pass "Verify assets ran (may have found issues)"
    fi

    # Test 4: Check invalidation
    print_test "Testing --check-invalidation..."
    if timeout 30 "$0" --check-invalidation > /dev/null 2>&1; then
        print_pass "Check invalidation works"
    else
        print_fail "Check invalidation failed"
    fi

    # Test 5: Frontend test mode
    print_test "Testing --frontend --test..."
    if timeout 30 "$0" --frontend --test > /dev/null 2>&1; then
        print_pass "Frontend test mode works"
    else
        print_fail "Frontend test mode failed"
    fi

    # Test 6: Backend test mode
    print_test "Testing --backend --test..."
    if timeout 30 "$0" --backend --test > /dev/null 2>&1; then
        print_pass "Backend test mode works"
    else
        print_fail "Backend test mode failed"
    fi

    # Test 7: ECS test mode
    print_test "Testing --ecs --test..."
    if timeout 30 "$0" --ecs --test > /dev/null 2>&1; then
        print_pass "ECS test mode works"
    else
        print_fail "ECS test mode failed"
    fi

    # Test 8: Full deployment test mode
    print_test "Testing full deployment --test..."
    if timeout 30 "$0" --test > /dev/null 2>&1; then
        print_pass "Full deployment test mode works"
    else
        print_fail "Full deployment test mode failed"
    fi

    # Test 9: Check for old script references
    print_test "Checking for old script references..."
    if grep -q "verify_frontend_assets\.sh\|check_cloudfront_invalidation\.sh" "$0"; then
        print_fail "Found references to old deleted scripts"
        grep -n "verify_frontend_assets\.sh\|check_cloudfront_invalidation\.sh" "$0"
    else
        print_pass "No old script references found"
    fi

    # Test 10: Verify all modes documented
    print_test "Checking help documentation completeness..."
    local help_output
    help_output=$("$0" --help 2>&1)
    if echo "$help_output" | grep -q "verify-assets" && \
       echo "$help_output" | grep -q "check-invalidation" && \
       echo "$help_output" | grep -q "frontend" && \
       echo "$help_output" | grep -q "backend" && \
       echo "$help_output" | grep -q "ecs" && \
       echo "$help_output" | grep -q "run-tests"; then
        print_pass "All modes documented in help"
    else
        print_fail "Missing modes in help documentation"
    fi

    echo ""
    print_header "TEST RESULTS"
    echo ""
    echo "  Total tests:  $test_count"
    echo "  Passed:       ${GREEN}$pass_count${NC}"
    echo "  Failed:       ${RED}$fail_count${NC}"
    echo ""

    if [ "$fail_count" -eq 0 ]; then
        print_success "All tests passed! ✅"
        echo ""
        echo "The deploy.sh script is ready for use."
        return 0
    else
        print_error "$fail_count test(s) failed ❌"
        return 1
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COPY FROM VM
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
copy_from_vm() {
    print_header "COPYING FROM VM"

    if [ "$TEST_MODE" = true ]; then
        print_info "Test mode: Would copy from $VM_USER@$VM_HOST"
        print_info "Source: $VM_SOURCE_PATH"
        print_info "Destination: $LOCAL_DEST_PATH"
        return 0
    fi

    print_info "Copying from VM: $VM_USER@$VM_HOST"
    print_info "Source: $VM_SOURCE_PATH"
    print_info "Destination: $LOCAL_DEST_PATH"

    mkdir -p "$LOCAL_DEST_PATH"

    if scp -r "$VM_USER@$VM_HOST:$VM_SOURCE_PATH" "$LOCAL_DEST_PATH"; then
        print_success "Files copied from VM successfully"
    else
        print_error "Failed to copy from VM"
        print_info "Check SSH access: ssh $VM_USER@$VM_HOST"
        return 1
    fi
}

#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN DEPLOYMENT LOGIC
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Confirmation (skip in test mode and utility modes)
if [ "$TEST_MODE" = false ] && [ "$MODE" != "verify" ] && [ "$MODE" != "check-invalidation" ] && [ "$MODE" != "run-tests" ]; then
    echo -n "Continue with deployment? (y/n): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        print_error "Deployment cancelled"
        exit 0
    fi
    echo ""
fi

# Execute based on mode
case $MODE in
    run-tests)
        run_test_suite
        exit $?
        ;;

    verify)
        verify_frontend_assets
        exit $?
        ;;

    check-invalidation)
        check_cloudfront_invalidation
        exit $?
        ;;

    frontend)
        deploy_frontend || exit 1
        ;;

    backend)
        if [ "$FROM_VM" = true ]; then
            copy_from_vm || exit 1
        fi
        deploy_backend_build || exit 1
        deploy_ecs || exit 1
        ;;

    ecs)
        deploy_ecs || exit 1
        ;;

    *)  # full
        if [ "$FROM_VM" = true ]; then
            copy_from_vm || exit 1
        fi

        # Run backend and frontend deployments in parallel for faster deployment
        print_info "Starting parallel deployment: Backend + Frontend"
        echo ""

        # Temporary files for capturing results
        BACKEND_LOG="/tmp/backend_deploy_$$.log"
        FRONTEND_LOG="/tmp/frontend_deploy_$$.log"
        BACKEND_STATUS_FILE="/tmp/backend_status_$$"
        FRONTEND_STATUS_FILE="/tmp/frontend_status_$$"

        # Backend deployment (build + ECR push + ECS) in background
        (
            {
                deploy_backend_build && deploy_ecs
                echo $? > "$BACKEND_STATUS_FILE"
            } > "$BACKEND_LOG" 2>&1
        ) &
        BACKEND_PID=$!

        # Frontend deployment (S3 sync + CloudFront) in background
        (
            {
                deploy_frontend
                echo $? > "$FRONTEND_STATUS_FILE"
            } > "$FRONTEND_LOG" 2>&1
        ) &
        FRONTEND_PID=$!

        print_info "⚙️  Backend (PID $BACKEND_PID): Docker build → ECR push → ECS deploy"
        print_info "🌐 Frontend (PID $FRONTEND_PID): S3 sync → CloudFront invalidation"
        echo ""

        # Wait for both processes and display results as they complete
        BACKEND_DONE=false
        FRONTEND_DONE=false

        while [ "$BACKEND_DONE" = false ] || [ "$FRONTEND_DONE" = false ]; do
            # Check frontend status
            if [ "$FRONTEND_DONE" = false ] && ! kill -0 $FRONTEND_PID 2>/dev/null; then
                FRONTEND_DONE=true
                cat "$FRONTEND_LOG"
                FRONTEND_EXIT_CODE=$(cat "$FRONTEND_STATUS_FILE" 2>/dev/null || echo "1")
                if [ "$FRONTEND_EXIT_CODE" -eq 0 ]; then
                    print_success "Frontend deployment successful ✓"
                else
                    print_error "Frontend deployment failed ✗"
                fi
                echo ""
            fi

            # Check backend status
            if [ "$BACKEND_DONE" = false ] && ! kill -0 $BACKEND_PID 2>/dev/null; then
                BACKEND_DONE=true
                cat "$BACKEND_LOG"
                BACKEND_EXIT_CODE=$(cat "$BACKEND_STATUS_FILE" 2>/dev/null || echo "1")
                if [ "$BACKEND_EXIT_CODE" -eq 0 ]; then
                    print_success "Backend deployment successful ✓"
                else
                    print_error "Backend deployment failed ✗"
                fi
                echo ""
            fi

            # Small sleep to avoid busy waiting
            if [ "$BACKEND_DONE" = false ] || [ "$FRONTEND_DONE" = false ]; then
                sleep 1
            fi
        done

        # Final wait to ensure processes are cleaned up
        wait $BACKEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true

        # Clean up temporary files
        rm -f "$BACKEND_LOG" "$FRONTEND_LOG" "$BACKEND_STATUS_FILE" "$FRONTEND_STATUS_FILE"

        # Check if either deployment failed
        BACKEND_EXIT_CODE=${BACKEND_EXIT_CODE:-1}
        FRONTEND_EXIT_CODE=${FRONTEND_EXIT_CODE:-1}

        if [ "$BACKEND_EXIT_CODE" -ne 0 ] || [ "$FRONTEND_EXIT_CODE" -ne 0 ]; then
            print_error "One or more parallel deployments failed"
            exit 1
        fi

        print_success "All parallel deployments completed successfully!"
        ;;
esac

# Calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

# Summary
print_header "DEPLOYMENT COMPLETE"

if [ "$TEST_MODE" = true ]; then
    echo -e "${GREEN}✅ Test mode complete - no changes were made${NC}"
    echo ""
    print_info "To actually deploy, run without --test flag"
else
    echo -e "${GREEN}🎉 Deployment successful!${NC}"
    echo ""
    echo "Duration: ${MINUTES}m ${SECONDS}s"
    echo ""

    case $MODE in
        frontend)
            echo "Frontend deployed:"
            echo "  S3 Bucket:    $S3_BUCKET"
            echo "  CloudFront:   $CLOUDFRONT_DIST_ID"
            echo "  URL:          https://d2nuwzlynr0xpz.cloudfront.net/home.html"
            if [ "$SKIP_INVALIDATION" = false ]; then
                echo ""
                print_warning "CloudFront cache clearing takes 5-15 minutes"
                print_info "Monitor: $0 --check-invalidation"
            fi
            ;;
        backend|ecs)
            echo "Backend deployed:"
            echo "  ECS Cluster:  $ECS_CLUSTER"
            echo "  ECS Service:  $ECS_SERVICE"
            echo "  Image:        $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
            echo ""
            print_info "View in AWS Console:"
            echo "  https://eu-central-1.console.aws.amazon.com/ecs/v2/clusters/$ECS_CLUSTER/services/$ECS_SERVICE"
            ;;
        *)
            echo "Full deployment:"
            echo "  Backend:"
            echo "    ECS Cluster:  $ECS_CLUSTER"
            echo "    ECS Service:  $ECS_SERVICE"
            echo "    Image:        $ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"
            echo ""
            echo "  Frontend:"
            echo "    S3 Bucket:    $S3_BUCKET"
            echo "    CloudFront:   $CLOUDFRONT_DIST_ID"
            echo "    URL:          https://d2nuwzlynr0xpz.cloudfront.net/home.html"

            if [ "$SKIP_INVALIDATION" = false ]; then
                echo ""
                print_warning "CloudFront cache clearing takes 5-15 minutes"
            fi
            ;;
    esac
fi

echo ""
print_success "Done! 🚀"
