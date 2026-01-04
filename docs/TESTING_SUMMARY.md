# Testing OPENAI_API_KEY in AWS ECS - Quick Summary

## What Was Done

I've added testing capabilities to verify that the `OPENAI_API_KEY` and other environment variables are properly loaded in AWS ECS.

## Files Created/Modified

### 1. Modified: [backend/api.py](backend/api.py)
- **Added:** New test endpoint `/api/test/env-check` (lines 843-877)
- **Purpose:** Safely check if environment variables are loaded (with masking for security)

### 2. Created: [AWS_ECS_ENV_TESTING.md](AWS_ECS_ENV_TESTING.md)
- Comprehensive guide on how to configure and test environment variables in AWS ECS
- Covers 3 methods: Task Definition, AWS Secrets Manager, and Parameter Store
- Includes complete step-by-step testing instructions

### 3. Created: [test_env_check.sh](test_env_check.sh)
- Bash script to easily test the environment check endpoint
- Supports testing: local Docker, ECS tasks, ALB, and CloudFront

### 4. Created: [setup_aws_secrets.sh](setup_aws_secrets.sh)
- Helper script to create AWS Secrets Manager secrets
- Automatically generates task definition JSON snippets
- Outputs required IAM policies

## Quick Start Testing

### Step 1: Test Locally First
```bash
# Make sure you have a .env file with your API key
cd backend
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-your-actual-key

# Start the application
cd ..
docker compose up --build

# In another terminal, test the endpoint
./test_env_check.sh local
```

**Expected Output:**
```json
{
  "environment": "local/docker",
  "ecs_metadata_available": false,
  "openai_api_key_present": true,
  "openai_api_key_masked": "sk-p...xyz1",
  "openai_api_key_length": 51,
  ...
}
```

### Step 2: Setup AWS Secrets (Optional but Recommended)
```bash
# This script will create secrets in AWS Secrets Manager
./setup_aws_secrets.sh

# Follow the prompts to enter your API keys
# The script will output the ARNs and policy JSON you need
```

### Step 3: Deploy to ECS
1. Build and push Docker image to ECR
2. Create/update ECS task definition with secrets
3. Deploy the service

### Step 4: Test in ECS
```bash
# Get your ECS task public IP from the AWS Console or CLI
# Then run:
./test_env_check.sh ecs <task-public-ip>
```

**Expected Output in ECS:**
```json
{
  "environment": "ECS",
  "ecs_metadata_available": true,
  "openai_api_key_present": true,
  "openai_api_key_masked": "sk-p...xyz1",
  ...
}
```

## Understanding the Results

### ✅ Success Indicators
- `"openai_api_key_present": true` - API key is loaded
- `"openai_api_key_length": 51` - Standard OpenAI key length
- `"openai_api_key_masked": "sk-p...xyz1"` - First/last 4 chars visible
- `"environment": "ECS"` - Running in ECS (when deployed)
- `"ecs_metadata_available": true` - ECS metadata service accessible

### ❌ Failure Indicators
- `"openai_api_key_present": false` - API key NOT loaded
- `"openai_api_key_length": 0` - No key found
- `"openai_api_key_masked": null` - No value to mask

## Common Issues and Solutions

### Issue 1: API Key Not Loaded in ECS
**Symptoms:** `"openai_api_key_present": false` in ECS

**Solutions:**
1. Verify secret exists in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id myaccessibilitybuddy/openai-api-key
   ```

2. Check task execution role has permissions:
   ```bash
   aws iam list-attached-role-policies --role-name ecsTaskExecutionRole
   ```

3. Verify ARN in task definition matches secret ARN

4. Check CloudWatch logs for errors:
   ```bash
   aws logs tail /ecs/myaccessibilitybuddy --follow
   ```

### Issue 2: .env File Not Working in ECS
**Explanation:** The `.env` file is mounted as a Docker volume in local development, but ECS has no host filesystem to mount from.

**Solution:** Use AWS Secrets Manager or environment variables in the task definition instead.

### Issue 3: Endpoint Returns 404
**Possible causes:**
- Service not started yet (check health check)
- Wrong port (should be 8000 for API)
- Security group blocking traffic

## How It Works

### Local Development (Docker Compose)
```
.env file → python-dotenv → os.environ → Application
```

### AWS ECS
```
Secrets Manager → ECS Task → Container env vars → os.environ → Application
                                  ↓
                          (python-dotenv skipped,
                           .env file not present)
```

### The Code Flow
1. [backend/api.py:22-26](backend/api.py#L22-L26) - Tries to load .env with python-dotenv
2. If .env not found (like in ECS), silently continues
3. [backend/api.py:853](backend/api.py#L853) - Reads from `os.environ.get('OPENAI_API_KEY')`
4. Works in both local (from .env) and ECS (from Secrets Manager)

## Security Notes

### ⚠️ Important Security Warnings

1. **Test Endpoint Exposure**
   - The `/api/test/env-check` endpoint exposes partial API key info
   - While masked, it still shows first/last 4 characters
   - **REMOVE or SECURE this endpoint in production!**

2. **Removing the Test Endpoint**
   ```python
   # Delete lines 843-877 in backend/api.py
   # Or add authentication as shown in AWS_ECS_ENV_TESTING.md
   ```

3. **Best Practices**
   - ✅ Use AWS Secrets Manager in production
   - ✅ Enable CloudTrail to audit secret access
   - ✅ Use least privilege IAM roles
   - ✅ Rotate secrets regularly
   - ❌ Never commit `.env` files to git
   - ❌ Never hardcode API keys in code
   - ❌ Never use plaintext environment variables in task definitions

## Architecture Overview

### Current Setup
```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Container                        │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │    │   Backend    │    │  OAuth Flow  │  │
│  │   (8080)     │    │   (8000)     │    │   (3001)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                            │                                 │
│                            ├─ /api/health                    │
│                            ├─ /api/generate-alt-text         │
│                            ├─ /api/test/env-check (NEW)      │
│                            └─ /api/auth/status               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  Environment Vars │
                    │  - OPENAI_API_KEY │
                    │  - CLIENT_ID_U2A  │
                    │  - etc.           │
                    └───────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
            Local Development      AWS ECS
                    │                    │
              ┌─────▼─────┐      ┌──────▼──────┐
              │ .env file │      │   Secrets   │
              │  (volume) │      │   Manager   │
              └───────────┘      └─────────────┘
```

## What to Do Next

### For Local Testing
1. ✅ Test locally with `./test_env_check.sh local`
2. ✅ Verify the endpoint works and shows your API key is loaded
3. ✅ Test the main functionality (generate alt-text) still works

### For AWS ECS Deployment
1. ✅ Run `./setup_aws_secrets.sh` to create secrets
2. ✅ Create ECS task definition with secrets ARNs
3. ✅ Deploy to ECS
4. ✅ Test with `./test_env_check.sh ecs <ip>`
5. ⚠️ **Remove test endpoint before production use!**

### For Production
1. ⚠️ Remove or secure `/api/test/env-check` endpoint
2. ✅ Use AWS Secrets Manager for all secrets
3. ✅ Enable automatic secret rotation
4. ✅ Set up CloudWatch alarms for failed health checks
5. ✅ Use Application Load Balancer with HTTPS
6. ✅ Configure proper CORS origins (not `allow_origins=["*"]`)

## Additional Resources

- **Detailed Guide:** [AWS_ECS_ENV_TESTING.md](AWS_ECS_ENV_TESTING.md)
- **AWS Secrets Manager Docs:** https://docs.aws.amazon.com/secretsmanager/
- **ECS Task Definition Docs:** https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html
- **OpenAI API Keys:** https://platform.openai.com/api-keys

## Questions?

If you encounter issues:
1. Check the [AWS_ECS_ENV_TESTING.md](AWS_ECS_ENV_TESTING.md) troubleshooting section
2. Review CloudWatch logs: `aws logs tail /ecs/myaccessibilitybuddy --follow`
3. Verify IAM permissions on the task execution role
4. Test secrets access manually with AWS CLI

---

**Remember:** The test endpoint `/api/test/env-check` is for testing only. Remove or secure it before deploying to production!
