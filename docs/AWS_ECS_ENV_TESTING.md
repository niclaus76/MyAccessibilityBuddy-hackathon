# Testing OPENAI_API_KEY Visibility in AWS ECS

## Overview
This guide explains how to test whether the `OPENAI_API_KEY` and other environment variables are properly loaded in AWS ECS.

## Test Endpoint Added
A new test endpoint has been added to the API:

**Endpoint:** `GET /api/test/env-check`

**Purpose:** Check if environment variables are properly loaded in the ECS container.

### Response Format
```json
{
  "environment": "ECS" | "local/docker",
  "ecs_metadata_available": true/false,
  "openai_api_key_present": true/false,
  "openai_api_key_masked": "sk-p...xyz1",
  "openai_api_key_length": 51,
  "client_id_u2a_present": true/false,
  "client_id_u2a_masked": "abcd...xyz1",
  "client_secret_u2a_present": true/false,
  "client_secret_u2a_masked": "abcd...xyz1",
  "dotenv_loaded": true/false,
  "warning": "This endpoint exposes partial credential info - disable in production!"
}
```

## How to Set Environment Variables in AWS ECS

### Method 1: ECS Task Definition (Recommended)
Add environment variables directly in your ECS task definition JSON:

```json
{
  "containerDefinitions": [
    {
      "name": "myaccessibilitybuddy",
      "image": "your-ecr-repo/myaccessibilitybuddy:latest",
      "environment": [
        {
          "name": "OPENAI_API_KEY",
          "value": "sk-your-actual-key-here"
        }
      ]
    }
  ]
}
```

**⚠️ WARNING:** This stores secrets in plaintext in the task definition. Not recommended for production!

### Method 2: AWS Secrets Manager (Production Recommended)
Store secrets in AWS Secrets Manager and reference them in the task definition:

```json
{
  "containerDefinitions": [
    {
      "name": "myaccessibilitybuddy",
      "image": "your-ecr-repo/myaccessibilitybuddy:latest",
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:openai-api-key-xxxxx"
        },
        {
          "name": "CLIENT_ID_U2A",
          "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:u2a-client-id-xxxxx"
        },
        {
          "name": "CLIENT_SECRET_U2A",
          "valueFrom": "arn:aws:secretsmanager:region:account-id:secret:u2a-client-secret-xxxxx"
        }
      ]
    }
  ]
}
```

**Required IAM Permissions:**
Your ECS task execution role needs:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:region:account-id:secret:*"
      ]
    }
  ]
}
```

### Method 3: AWS Systems Manager Parameter Store
Similar to Secrets Manager but using Parameter Store:

```json
{
  "containerDefinitions": [
    {
      "name": "myaccessibilitybuddy",
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:ssm:region:account-id:parameter/myaccessibilitybuddy/openai-api-key"
        }
      ]
    }
  ]
}
```

## Testing Steps

### 1. Local Docker Testing
First, test locally with Docker to ensure the app works:

```bash
# Create .env file
cd backend
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Build and run with docker-compose
cd ..
docker compose up --build

# Test the endpoint
curl http://localhost:8000/api/test/env-check
```

Expected output:
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

### 2. Push to ECR
```bash
# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

# Tag and push
docker tag myaccessibilitybuddy:latest <account-id>.dkr.ecr.<region>.amazonaws.com/myaccessibilitybuddy:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/myaccessibilitybuddy:latest
```

### 3. Create ECS Task Definition with Secrets
Create a file `task-definition.json`:

```json
{
  "family": "myaccessibilitybuddy",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<account-id>:role/myaccessibilitybuddyTaskRole",
  "containerDefinitions": [
    {
      "name": "myaccessibilitybuddy",
      "image": "<account-id>.dkr.ecr.<region>.amazonaws.com/myaccessibilitybuddy:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        },
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:<region>:<account-id>:secret:myaccessibilitybuddy/openai-api-key-xxxxx"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/myaccessibilitybuddy",
          "awslogs-region": "<region>",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "python3 -c 'import requests; requests.get(\"http://localhost:8000/api/health\", timeout=5)'"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 40
      }
    }
  ]
}
```

### 4. Register Task Definition
```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### 5. Create/Update ECS Service
```bash
aws ecs create-service \
  --cluster <cluster-name> \
  --service-name myaccessibilitybuddy \
  --task-definition myaccessibilitybuddy \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### 6. Test in ECS
Once the service is running:

```bash
# Get the public IP of the task
aws ecs list-tasks --cluster <cluster-name> --service-name myaccessibilitybuddy
aws ecs describe-tasks --cluster <cluster-name> --tasks <task-arn>

# Test the endpoint
curl http://<task-public-ip>:8000/api/test/env-check
```

Expected output in ECS:
```json
{
  "environment": "ECS",
  "ecs_metadata_available": true,
  "openai_api_key_present": true,
  "openai_api_key_masked": "sk-p...xyz1",
  "openai_api_key_length": 51,
  ...
}
```

## Troubleshooting

### Environment Variable Not Loaded

**Problem:** `openai_api_key_present: false`

**Solutions:**
1. Check ECS task logs:
   ```bash
   aws logs tail /ecs/myaccessibilitybuddy --follow
   ```

2. Verify Secrets Manager secret exists:
   ```bash
   aws secretsmanager get-secret-value --secret-id myaccessibilitybuddy/openai-api-key
   ```

3. Check IAM permissions on task execution role:
   ```bash
   aws iam get-role --role-name ecsTaskExecutionRole
   aws iam list-attached-role-policies --role-name ecsTaskExecutionRole
   ```

4. Verify the secret ARN in task definition matches the actual secret ARN

### .env File Not Working in ECS

**Problem:** `.env` file approach doesn't work in ECS

**Explanation:**
- In the current Docker setup, the `.env` file is mounted as a volume from the host
- In ECS, there's no host filesystem to mount from
- The `.env` file approach only works with docker-compose locally

**Solution:**
- Use environment variables in the task definition OR
- Use AWS Secrets Manager/Parameter Store (recommended)
- The `python-dotenv` will be skipped, and environment variables will be read directly from `os.environ`

## Security Best Practices

1. **Never commit `.env` files to git** - Already in `.gitignore`
2. **Use AWS Secrets Manager in production** - Automatic rotation, encryption at rest
3. **Remove the test endpoint in production** - Or add authentication/authorization
4. **Use least privilege IAM roles** - Only grant necessary permissions
5. **Enable CloudTrail** - Audit secret access
6. **Rotate secrets regularly** - Use AWS Secrets Manager rotation features

## Alternative: Using CloudFront + ALB
If you're using CloudFront and ALB (Application Load Balancer):

```
User -> CloudFront -> ALB -> ECS Service -> Container
```

The environment variables are still set at the ECS task level, regardless of the upstream infrastructure.

## Monitoring

Monitor secret access in CloudWatch Logs:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/myaccessibilitybuddy \
  --filter-pattern "OPENAI_API_KEY"
```

## Clean Up Test Endpoint

Once testing is complete, remove or secure the test endpoint:

```python
# Option 1: Delete the endpoint entirely
# Remove lines 843-877 from api.py

# Option 2: Add authentication
from fastapi import Depends, HTTPException, Header

async def verify_admin_token(x_admin_token: str = Header(...)):
    if x_admin_token != os.environ.get("ADMIN_TOKEN"):
        raise HTTPException(status_code=403, detail="Forbidden")

@app.get("/api/test/env-check", dependencies=[Depends(verify_admin_token)])
async def test_env_check():
    # ... existing code ...
```

## Conclusion

The test endpoint will help you verify that:
1. Environment variables are properly loaded in ECS
2. AWS Secrets Manager integration works correctly
3. The application can access the OPENAI_API_KEY
4. All credential management is working as expected

Remember to remove or secure this endpoint before deploying to production!
