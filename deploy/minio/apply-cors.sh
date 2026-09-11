# Apply with a MinIO administration client from a trusted host.
mc alias set plm-control http://10.1.58.6:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
for bucket in plm-quarantine-lab plm-draft-lab plm-release-lab plm-export-lab; do
  mc cors set plm-control/$bucket /path/to/cors.json
done
