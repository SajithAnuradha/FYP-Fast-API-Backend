---
title: FYP FastAPI Backend
emoji: "🚀"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# FYP-Fast-API-Backend

## Usage collection without a database

This backend now supports append-only request logging for the `/generate-patch` API without requiring a database.

- Default log file: `data/usage_logs/generate_patch_requests.jsonl`
- Override path with: `USAGE_LOG_PATH=/custom/path/usage.jsonl`

Each line is a JSON object containing:

- UTC timestamp for when the backend was used
- Request route and HTTP method
- Client metadata such as IP address and user agent when available
- Bug report payload including selected buggy lines, surrounding context, and natural language feedback
- Result metadata including success/failure, patch count, and error message

JSON Lines is a better fit than CSV here because the stored data is nested and audit-oriented. It stays simple to append, read, rotate, and ship elsewhere later if you eventually move to a real database or analytics pipeline.
