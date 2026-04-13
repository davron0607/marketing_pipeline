#!/bin/sh
# Run after MinIO starts to create the default bucket
mc alias set local http://minio:9000 minioadmin minioadmin
mc mb --ignore-existing local/survey-datasets
mc anonymous set download local/survey-datasets
echo "MinIO bucket initialized."
