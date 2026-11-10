# Optional local container recipe. Not a production deployment.
FROM python:3.12-slim
WORKDIR /app
COPY ingredient_api ./ingredient_api
COPY data ./data
COPY docs ./docs
COPY openapi.json ./openapi.json
COPY LICENSE LICENSE-DATA NOTICE.md ./
USER 65534:65534
EXPOSE 8000
CMD ["python", "-m", "ingredient_api", "--host", "0.0.0.0", "--port", "8000"]
