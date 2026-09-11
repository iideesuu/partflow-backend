# PartFlow production deployment on 10.1.58.13

Use `s3.chipedgetech.com` as the browser-facing MinIO S3 endpoint. It must resolve to 10.1.58.13 and use a certificate whose SAN covers the hostname. Install `nginx/s3.chipedgetech.com.conf` under `/etc/nginx/conf.d/` and validate with `nginx -t`.

Set the backend environment from `production.env.example`: `MINIO_S3_PUBLIC_ENDPOINT=https://s3.chipedgetech.com`, `MINIO_S3_CONTROL_ENDPOINT=http://10.1.58.6:9000`, and `MINIO_CONSOLE_URL=http://10.1.58.6:9001`. The public and control endpoints must remain distinct.

The two subdomains are different origins, so this configuration still requires the MinIO CORS policy in `minio/cors.json`. It avoids mixed content and preserves the SigV4 Host. Do not rewrite the S3 URI or expose port 9001 as an upload endpoint.
