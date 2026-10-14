#!/bin/sh
# Controlled release: build immutable image -> push -> migrate (one-off task) -> roll the service.
# Usage: PRIVATE_SUBNET=subnet-.. APP_SG=sg-.. deploy/aws/release.sh <env> <region> <ecr-repo-uri> [image-tag]
# Rollback: re-run with the previous good tag as 4th arg (skips build; still runs migrate, which is a no-op
# for already-applied migrations). Migrations are forward-only; see docs/phase15/runbook.md.
set -eu
ENV=$1; REGION=$2; REPO=$3; TAG=${4:-}
CL=pis-$ENV
if [ -z "$TAG" ]; then
  [ -z "$(git status --porcelain)" ] || { echo "dirty tree; release from a clean commit"; exit 1; }
  [ -d models/bundles ] || { echo "models/bundles missing: bake a promoted bundle into the image"; exit 1; }
  TAG=$(git rev-parse --short=12 HEAD)
  docker build -t "$REPO:$TAG" . && docker push "$REPO:$TAG"
fi
IMG="$REPO:$TAG"
cd "$(dirname "$0")"
# Register task definitions with the new image, without touching the running service yet.
terraform apply -auto-approve -var-file="$ENV.tfvars" -var "image=$IMG" \
  -target=aws_ecs_task_definition.migrate
ARN=$(aws ecs run-task --region "$REGION" --cluster "$CL" --launch-type FARGATE --task-definition "$CL-migrate" \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET],securityGroups=[$APP_SG],assignPublicIp=DISABLED}" \
  --query 'tasks[0].taskArn' --output text)
aws ecs wait tasks-stopped --region "$REGION" --cluster "$CL" --tasks "$ARN"
CODE=$(aws ecs describe-tasks --region "$REGION" --cluster "$CL" --tasks "$ARN" --query 'tasks[0].containers[0].exitCode' --output text)
[ "$CODE" = "0" ] || { echo "migration failed (exit $CODE); service NOT updated"; exit 1; }
terraform apply -auto-approve -var-file="$ENV.tfvars" -var "image=$IMG"
aws ecs wait services-stable --region "$REGION" --cluster "$CL" --services api
echo "released $IMG"
