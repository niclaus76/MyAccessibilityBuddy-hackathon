# Complete Deployment Guide

## 🎯 Quick Reference Card

### Universal Deployment Script: `deploy.sh`

All deployment functionality is now in **one script**:

```bash
# Most common commands:

# Frontend changes (HTML/CSS/JS)
./tools/deploy.sh --frontend

# Backend changes (API code)
./tools/deploy.sh --backend

# Full deployment
./tools/deploy.sh

# Preview mode (safe)
./tools/deploy.sh --test

# Fast mode (skip tests)
./tools/deploy.sh --fast
```

---

## 📦 Available Scripts

| Script | Purpose | When to Use |
|------|---------|-------------|
| **`deploy.sh`** | Universal deployment & utilities | All scenarios |
| `setup_aws_secrets.sh` | AWS secrets | Initial setup |
| `test_env_check.sh` | Env validation | Check configuration |

**Note:** `check_cloudfront_invalidation.sh` and `verify_frontend_assets.sh` have been **integrated into deploy.sh** as `--check-invalidation` and `--verify-assets` respectively.

---

## 🚀 Deployment Modes

The unified `deploy.sh` supports 7 modes:

| Mode | Command | Use When | Duration |
|------|---------|----------|----------|
| **Frontend** | `./tools/deploy.sh --frontend` | HTML, CSS, JS, assets changed | ~1 min + cache |
| **Backend** | `./tools/deploy.sh --backend` | API code changed | ~8-12 min |
| **ECS Only** | `./tools/deploy.sh --ecs` | Image already in ECR | ~3-5 min |
| **Full** | `./tools/deploy.sh` | Both frontend & backend | ~8-12 min (parallel) |
| **From VM** | `./tools/deploy.sh --from-vm` | Copy from VM first | ~10-15 min (parallel) |
| **Verify Assets** | `./tools/deploy.sh --verify-assets` | Check frontend files | < 1 second |
| **Check Invalidation** | `./tools/deploy.sh --check-invalidation` | Monitor CloudFront | < 5 seconds |
| **Run Tests** | `./tools/deploy.sh --run-tests` | Test script functionality | ~2 minutes |

**New:** Full deployments now run backend and frontend in **parallel** for 40% faster deployments!

---

## 🔧 All Options

```bash
./tools/deploy.sh [MODE] [OPTIONS]

MODES (choose one):
  (default)               Full deployment: Backend + Frontend (runs in parallel)
  --frontend              Frontend only: S3 sync + CloudFront invalidation
  --backend               Backend only: Docker build + ECR push + ECS deploy
  --ecs                   ECS update only: Deploy existing image to service
  --from-vm               Copy from VM first, then full deployment
  --verify-assets         Verify frontend assets (favicons, manifests, CDN)
  --check-invalidation    Check CloudFront invalidation status
  --run-tests             Run comprehensive test suite on the script

OPTIONS:
  -t, --test              Test mode: Preview changes without deploying
  -f, --fast              Fast mode: Skip local Docker container testing
  --skip-invalidation     Skip CloudFront cache invalidation
  --skip-monitor          Skip ECS deployment monitoring
  -d, --debug             Debug mode: Show detailed progress messages
  -q, --quiet             Quiet mode: Show only errors
  --tag <TAG>             Docker image tag (default: latest)
  -h, --help              Show this help message
```

---

## 📋 Common Workflows

### Workflow 1: Frontend Changes (HTML/CSS/JS)

**Use case:** Updated styles, markup, or client-side JavaScript

```bash
# Step 1: Preview what will change
./tools/deploy.sh --frontend --test

# Step 2: Deploy frontend (includes automatic status check)
./tools/deploy.sh --frontend
```

**Note:** CloudFront invalidation status is now checked automatically after deployment.

**What happens:**
1. ✅ Detects changed files
2. ✅ Syncs to S3
3. ✅ Invalidates CloudFront cache
4. ✅ Automatically checks invalidation status

**Duration:** ~1 minute (+ 5-15 min for CloudFront)

---

### Workflow 2: Backend API Changes

**Use case:** Backend code or API updates

```bash
# Deploy backend with local testing
./tools/deploy.sh --backend

# Or skip local testing if ports busy
./tools/deploy.sh --backend --fast
```

**What happens:**
1. ✅ Validates .env file
2. ✅ Builds Docker image
3. ✅ Tests container locally (unless --fast)
4. ✅ Pushes to ECR
5. ✅ Updates ECS task definition
6. ✅ Deploys to ECS service
7. ✅ Monitors deployment
8. ✅ Tests health endpoint

**Duration:** ~8-12 minutes

---

### Workflow 3: Full Deployment (Backend + Frontend)

**Use case:** New features affecting both backend and frontend

```bash
# Step 1: Verify frontend assets
./tools/deploy.sh --verify-assets

# Step 2: Deploy everything (runs in parallel!)
./tools/deploy.sh

# Step 3: Monitor CloudFront
./tools/deploy.sh --check-invalidation
```

**What happens (in parallel):**
- **Backend Stream:**
  1. ✅ Validates .env file
  2. ✅ Builds Docker image
  3. ✅ Tests container (optional)
  4. ✅ Pushes to ECR
  5. ✅ Updates ECS task definition
  6. ✅ Deploys to ECS service
  7. ✅ Monitors deployment

- **Frontend Stream (concurrent):**
  8. ✅ Syncs frontend to S3
  9. ✅ Invalidates CloudFront

**Duration:** ~8-12 minutes (40% faster than sequential!) (+ 5-15 min for CloudFront cache)

---

### Workflow 4: Emergency Hotfix

**Use case:** Critical bug fix needed quickly

```bash
# Skip all testing for speed
./tools/deploy.sh --fast
```

**Duration:** ~8-12 minutes

---

### Workflow 5: Deploy from VM

**Use case:** Code changes on VM need deployment

```bash
# Copy from VM and deploy
./tools/deploy.sh --from-vm

# Or with specific tag
./tools/deploy.sh --from-vm --tag hotfix-2026-01-03
```

**What happens:**
1. ✅ Copies files from VM via SCP
2. ✅ Same as full deployment

**Duration:** ~12-18 minutes

---

### Workflow 6: ECS Update Only

**Use case:** Image already in ECR, just update service

```bash
# Update ECS service
./tools/deploy.sh --ecs

# With specific tag
./tools/deploy.sh --ecs --tag v1.2.3

# Skip monitoring
./tools/deploy.sh --ecs --skip-monitor
```

**Duration:** ~3-5 minutes

---

## 🧪 Test Mode (Safe Preview)

**Always safe to run** - shows what would change without deploying:

```bash
# Preview frontend changes
./tools/deploy.sh --frontend --test

# Preview backend changes
./tools/deploy.sh --backend --test

# Preview full deployment
./tools/deploy.sh --test
```

**Test mode shows:**
- Files that would be uploaded/deleted
- Docker images that would be built
- ECS tasks that would be updated
- No actual deployments occur

---

## 🔊 Verbosity Levels

Control the amount of output during deployment:

### Normal Mode (default)
Shows informational messages, warnings, and errors:
```bash
./tools/deploy.sh --frontend
```

Output includes:
- ✅ Progress updates (blue ℹ)
- ⚠️ Warnings (yellow)
- ❌ Errors (red)
- ✅ Success messages (green)

### Debug Mode (`-d` or `--debug`)
Shows detailed progress with technical details:
```bash
./tools/deploy.sh --frontend --debug
```

Additional debug output:
- 🔍 AWS CLI commands being executed
- 🔍 Configuration values (regions, buckets, registries)
- 🔍 File paths and Docker commands
- 🔍 Tool version checks
- 🔍 Step-by-step execution details

**When to use:**
- Troubleshooting deployment issues
- Understanding what the script is doing
- Debugging AWS API calls
- Creating support tickets

### Quiet Mode (`-q` or `--quiet`)
Shows only errors and final results:
```bash
./tools/deploy.sh --backend --quiet
```

Output includes:
- ❌ Errors only
- ✅ Success/failure status
- No informational messages
- No warnings (unless critical)

**When to use:**
- CI/CD pipelines
- Cron jobs
- Automated deployments
- When you only care about success/failure

### Examples

```bash
# Debug a failing deployment
./tools/deploy.sh --frontend --debug

# Silent backend deployment for CI/CD
./tools/deploy.sh --backend --quiet

# Combine with test mode
./tools/deploy.sh --test --debug

# Quiet verify before deployment
./tools/deploy.sh --verify-assets --quiet
```

---

## 📊 Detailed Mode Explanations

### Full Deployment (default)

```bash
./tools/deploy.sh
```

**Steps:**
1. Build Docker image
2. Push to ECR
3. Update ECS task definition
4. Deploy to ECS service
5. Monitor deployment
6. Sync frontend to S3
7. Invalidate CloudFront

**Duration:** ~10-15 minutes

---

### Frontend Only

```bash
./tools/deploy.sh --frontend
```

**Steps:**
1. Detect changed files
2. Sync to S3 (with --exact-timestamps)
3. Invalidate CloudFront cache
4. Smart invalidation (targeted < 10 files, wildcard ≥ 10)

**Duration:** ~1 minute + cache (5-15 min)

**When to use:**
- HTML changes
- CSS/JavaScript updates
- Asset changes (images, icons)
- Quick frontend fixes

---

### Backend Only

```bash
./tools/deploy.sh --backend
```

**Steps:**
1. Check prerequisites (Docker, AWS CLI, jq)
2. Validate .env file
3. Build Docker image
4. Test container locally (unless --fast)
5. Login to ECR
6. Tag and push image
7. Update ECS task definition
8. Deploy to ECS service
9. Monitor deployment

**Duration:** ~8-12 minutes

**When to use:**
- Backend API changes
- Python code updates
- Dependency updates

---

### ECS Update Only

```bash
./tools/deploy.sh --ecs
```

**Steps:**
1. Retrieve current task definition
2. Create new task definition with updated image
3. Update ECS service
4. Monitor deployment
5. Get service endpoint
6. Test health endpoint

**Duration:** ~3-5 minutes

**When to use:**
- Image already in ECR
- Rollback to previous version
- Deploy specific tagged version

---

### From VM

```bash
./tools/deploy.sh --from-vm
```

**Steps:**
1. Copy files from VM via SCP
2. Same as full deployment

**Duration:** ~12-18 minutes

**When to use:**
- Development on VM
- Need to sync VM changes

---

## 🔍 What the Script Checks

### Prerequisites Check

- ✅ Docker installed and running
- ✅ AWS CLI installed
- ✅ jq installed (for JSON processing)
- ✅ AWS credentials configured
- ✅ .env file exists

### Smart Features

1. **Change Detection**: Only uploads changed files
2. **Port Conflict Handling**: Skips local test if port 8000 busy
3. **Health Checks**: Tests endpoints after deployment
4. **Real-time Monitoring**: Shows ECS deployment progress
5. **Smart Invalidation**: Targeted for < 10 files, wildcard for ≥ 10
6. **Deployment Timing**: Shows duration at end

---

## 🔧 Configuration

### AWS Resources

All configured in `deploy.sh`:

```bash
AWS_REGION="eu-central-1"
ECR_REGISTRY="514201995752.dkr.ecr.eu-central-1.amazonaws.com"
ECR_REPO="myaccessibilitybuddy-api"
S3_BUCKET="myaccessibilitybuddy-frontend-1"
CLOUDFRONT_DIST_ID="E1INLYHYA11V49"
ECS_CLUSTER="myaccessibilitybuddy-cluster"
ECS_SERVICE="myaccessibilitybuddy-service"
TASK_FAMILY="myaccessibilitybuddy-task"
```

### VM Configuration

```bash
VM_USER="developer"
VM_HOST="192.168.64.4"
VM_SOURCE_PATH="/home/developer/Innovate-For-Inclusion---MyAccessibilityBuddy"
LOCAL_DEST_PATH="$HOME/Documents/ECB/AWS-Caionen/"
```

### Frontend

```bash
FRONTEND_DIR="/home/developer/Innovate-For-Inclusion---MyAccessibilityBuddy/frontend"
```

---

## 📝 Post-Deployment Checklist

### 1. Verify Backend (ECS)

```bash
# Check service status
aws ecs describe-services \
  --cluster myaccessibilitybuddy-cluster \
  --services myaccessibilitybuddy-service \
  --region eu-central-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Check task health
aws ecs list-tasks \
  --cluster myaccessibilitybuddy-cluster \
  --service-name myaccessibilitybuddy-service \
  --region eu-central-1
```

### 2. Verify Frontend (S3 + CloudFront)

```bash
# Check CloudFront invalidation
./tools/deploy.sh --check-invalidation

# List recent S3 files
aws s3 ls s3://myaccessibilitybuddy-frontend-1/ --recursive | tail -10
```

### 3. Test Endpoints

**Backend Health Check:**
```bash
# Script shows public IP after deployment
curl http://<PUBLIC-IP>:8000/api/health
curl http://<PUBLIC-IP>:8000/api/available-providers
```

**Frontend:**
```
https://d2nuwzlynr0xpz.cloudfront.net/home.html
```

### 4. Monitor Logs

```bash
# View ECS logs
aws logs tail /ecs/myaccessibilitybuddy-task \
  --follow \
  --region eu-central-1

# Or in AWS Console:
# https://eu-central-1.console.aws.amazon.com/cloudwatch/home?region=eu-central-1#logsV2:log-groups
```

---

## 🐛 Troubleshooting

### Issue: Port 8000 Already in Use

**Solution:**
```bash
# Use fast mode to skip local testing
./tools/deploy.sh --backend --fast

# Or kill the process
lsof -Pi :8000 -sTCP:LISTEN -t | xargs kill -9
```

---

### Issue: ECS Deployment Stuck

**Check service events:**
```bash
aws ecs describe-services \
  --cluster myaccessibilitybuddy-cluster \
  --services myaccessibilitybuddy-service \
  --query 'services[0].events[0:5]'
```

**Check task failures:**
```bash
aws ecs describe-tasks \
  --cluster myaccessibilitybuddy-cluster \
  --tasks $(aws ecs list-tasks \
    --cluster myaccessibilitybuddy-cluster \
    --service-name myaccessibilitybuddy-service \
    --query 'taskArns[0]' --output text)
```

**Skip monitoring:**
```bash
./tools/deploy.sh --backend --skip-monitor
```

---

### Issue: CloudFront Still Showing Old Content

**Solutions:**
1. Wait 5-15 minutes for invalidation
2. Check status: `./tools/deploy.sh --check-invalidation`
3. Hard refresh browser: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
4. Test with curl: `curl -I https://d2nuwzlynr0xpz.cloudfront.net/home.html`

---

### Issue: Frontend Assets Missing (403/404)

**Check S3:**
```bash
# Verify assets exist
aws s3 ls s3://myaccessibilitybuddy-frontend-1/assets/

# Verify frontend assets
./tools/deploy.sh --verify-assets

# Re-sync frontend
./tools/deploy.sh --frontend
```

---

### Issue: Docker Build Fails

**Solutions:**
```bash
# Check .env file exists
ls -la backend/.env

# Check Docker is running
docker info

# Clean Docker cache
docker system prune -f

# Try build manually
docker build -t test .
```

---

### Issue: AWS Credentials Not Working

**Check credentials:**
```bash
# List configuration
aws configure list

# Check identity
aws sts get-caller-identity

# Reconfigure if needed
aws configure
```

---

## 🎯 Best Practices

### 1. Always verify before deploying

```bash
./tools/deploy.sh --verify-assets
```

### 2. Use test mode for preview

```bash
./tools/deploy.sh --frontend --test
```

### 3. Use fast mode when ports are busy

```bash
./tools/deploy.sh --backend --fast
```

### 4. Monitor deployments

- Watch ECS deployment progress (automatic unless --skip-monitor)
- Check CloudFront invalidation status
- Test endpoints after deployment

### 5. Keep deployments modular

- Frontend changes → `./tools/deploy.sh --frontend`
- Backend changes → `./tools/deploy.sh --backend`
- Both → `./tools/deploy.sh`

### 6. Check logs if issues occur

```bash
aws logs tail /ecs/myaccessibilitybuddy-task --follow
```

### 7. Tag important deployments

```bash
./tools/deploy.sh --tag v1.2.3
./tools/deploy.sh --tag production-2026-01-03
```

---

## 📚 Additional Resources

### Documentation

- [QUICK_START.md](QUICK_START.md) - Quick reference card
- [BOOTSTRAP_ITALIA_FIX.md](../docs/BOOTSTRAP_ITALIA_FIX.md) - Frontend fixes

### AWS Console Links

- [ECS Cluster](https://eu-central-1.console.aws.amazon.com/ecs/v2/clusters/myaccessibilitybuddy-cluster)
- [ECR Repository](https://eu-central-1.console.aws.amazon.com/ecr/repositories/private/514201995752/myaccessibilitybuddy-api)
- [S3 Bucket](https://s3.console.aws.amazon.com/s3/buckets/myaccessibilitybuddy-frontend-1)
- [CloudFront Distribution](https://console.aws.amazon.com/cloudfront/v3/home?#/distributions/E1INLYHYA11V49)

### Command Reference

```bash
# List all deployment scripts
ls -lh tools/*.sh

# View script help
./tools/deploy.sh --help

# Check AWS configuration
aws configure list
aws sts get-caller-identity

# Check CloudFront invalidation
./tools/deploy.sh --check-invalidation

# Verify frontend assets
./tools/deploy.sh --verify-assets
```

---

## 📊 Integrated Utility Commands

### --check-invalidation

**Purpose:** Monitor CloudFront cache invalidation progress

**Usage:**
```bash
./tools/deploy.sh --check-invalidation
```

**Shows:**
- List of recent invalidations
- Status (Completed/InProgress)
- Details of latest invalidation
- Paths being invalidated
- Estimated completion time

**Example Output:**
```
Recent Invalidations:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ID                   STATUS          CREATE TIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
E2XAMPLE123       Completed       2026-01-03 14:30:22
E2XAMPLE124       InProgress      2026-01-03 15:45:10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Latest Invalidation Details:
ID:              E2XAMPLE124
Status:          InProgress
Create Time:     2026-01-03T15:45:10.123Z
Paths:           /*

⚠️  Latest invalidation is still in progress
ℹ This typically takes 5-15 minutes
```

---

### --verify-assets

**Purpose:** Pre-deployment verification of frontend assets

**Usage:**
```bash
./tools/deploy.sh --verify-assets
```

**Checks:**
- ✅ All 6 favicon files exist
- ✅ Manifest files (webmanifest, browserconfig.xml)
- ✅ Favicon links in HTML
- ✅ Theme color meta tags
- ✅ Bootstrap Italia CDN references
- ✅ No old local sprite references

**Example Output:**
```
Checking favicon files...
✅ assets/favicon.ico (935)
✅ assets/favicon-16x16.png (913)
✅ assets/favicon-32x32.png (2.8K)
✅ assets/apple-touch-icon.png (38K)
✅ assets/android-chrome-192x192.png (42K)
✅ assets/android-chrome-512x512.png (294K)

🎉 All checks passed! Frontend assets are ready.
```

---

### --run-tests

**Purpose:** Comprehensive test suite for the deploy.sh script

**Usage:**
```bash
./tools/deploy.sh --run-tests
```

**Tests Performed:**
1. ✅ Bash syntax validation
2. ✅ Help command functionality
3. ✅ Verify assets mode
4. ✅ Check invalidation mode
5. ✅ Frontend test mode
6. ✅ Backend test mode
7. ✅ ECS test mode
8. ✅ Full deployment test mode
9. ✅ No old script references
10. ✅ Help documentation completeness

**Example Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TEST RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total tests:  10
Passed:       10
Failed:       0

✅ All tests passed! ✅

The deploy.sh script is ready for use.
```

**When to use:**
- After modifying deploy.sh
- Before important deployments
- To verify script integrity
- In CI/CD pipelines

---

## 🆕 What Changed (Migration from Multiple Scripts)

### Previous System (5 scripts)

- `deploy_complete.sh` - Full deployment orchestrator
- `deploy_vm_to_aws.sh` - VM to AWS deployment
- `deploy_ecs_update.sh` - ECS updates
- `quick_frontend_update.sh` - Frontend sync
- `sync_frontend_smart.sh` - Advanced frontend sync

### New System (1 unified script)

**`deploy.sh`** - All functionality merged

**Benefits:**
- ✅ Single entry point
- ✅ Consistent interface
- ✅ Less confusion
- ✅ Easier maintenance
- ✅ All features in one place

**Migration:**
```bash
# Old → New
deploy_complete.sh              → ./tools/deploy.sh
deploy_complete.sh --fast       → ./tools/deploy.sh --fast
deploy_vm_to_aws.sh             → ./tools/deploy.sh --from-vm
deploy_ecs_update.sh            → ./tools/deploy.sh --ecs
quick_frontend_update.sh        → ./tools/deploy.sh --frontend
sync_frontend_smart.sh --test   → ./tools/deploy.sh --frontend --test
```

---

## 📈 Decision Guide

**Which mode should I use?**

```
Changed HTML/CSS/JS only?
  └─ ./tools/deploy.sh --frontend

Changed backend API code?
  └─ ./tools/deploy.sh --backend

Changed both frontend and backend?
  └─ ./tools/deploy.sh

Image already in ECR?
  └─ ./tools/deploy.sh --ecs

Code is on VM?
  └─ ./tools/deploy.sh --from-vm

Want to preview first?
  └─ Add --test to any command

Port 8000 busy?
  └─ Add --fast to any command

Need specific version?
  └─ Add --tag v1.2.3 to any command
```

---

## ⚡ Recent Updates (v3.0)

### January 4, 2026 - Parallel Deployment & Script Consolidation

**Major improvements:**
- ✅ **Parallel deployment:** Backend and frontend now deploy concurrently (40% faster)
- ✅ **Script consolidation:** Integrated `verify_frontend_assets.sh` and `check_cloudfront_invalidation.sh` into `deploy.sh`
- ✅ **New modes:** `--verify-assets` and `--check-invalidation`
- ✅ **Simplified tooling:** Reduced from multiple scripts to one unified tool

**Migration:**
```bash
# Old commands → New commands
./tools/verify_frontend_assets.sh        → ./tools/deploy.sh --verify-assets
./tools/check_cloudfront_invalidation.sh → ./tools/deploy.sh --check-invalidation
```

See [DEPLOY_OPTIMIZATION.md](DEPLOY_OPTIMIZATION.md) for full details.

---

**Last Updated:** 2026-01-04
**Version:** 3.0 (Parallel + Consolidated)
