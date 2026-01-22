#!/bin/bash

set -e

TARGET_IP=$1
SSH_USER=$2
IMAGE_NAME=$3
IMAGE_TAG=$4
BUILD_FLAG=$5

if [ -z "$TARGET_IP" ] || [ -z "$SSH_USER" ] || [ -z "$IMAGE_NAME" ] || [ -z "$IMAGE_TAG" ]; then
  echo "USAGE:"
  echo "./export_container.sh <TARGET_IP> <SSH_USER> <IMAGE_NAME> <IMAGE_TAG> [--build]"
  exit 1
fi

ARCH=$(uname -m)
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
TAR_FILE="${IMAGE_NAME}_${IMAGE_TAG}.tar"

echo "Target host: $TARGET_IP"
echo "Image: $IMAGE_REF"
echo "Architecture: $ARCH"

# Step 1. Optional build
if [ "$BUILD_FLAG" == "--build" ]; then
  echo "Building image locally on VM..."
  docker build -t "$IMAGE_REF" .
fi

# Step 2. Verify image exists
if ! docker image inspect "$IMAGE_REF" > /dev/null 2>&1; then
  echo "ERROR: Image $IMAGE_REF does not exist."
  exit 1
fi

# Step 3. Export image
echo "Exporting Docker image..."
docker save "$IMAGE_REF" -o "$TAR_FILE"

# Step 4. Copy to Mac
echo "Copying image to target host..."
scp "$TAR_FILE" "${SSH_USER}@${TARGET_IP}:/tmp/"

# Step 5. Load image on Mac
echo "Loading image on target host..."
ssh "${SSH_USER}@${TARGET_IP}" "docker load -i /tmp/${TAR_FILE}"

# Step 6. Cleanup
echo "Cleaning up temporary files..."
rm "$TAR_FILE"
ssh "${SSH_USER}@${TARGET_IP}" "rm /tmp/${TAR_FILE}"

echo "SUCCESS"
echo "Image $IMAGE_REF is now available on $TARGET_IP"