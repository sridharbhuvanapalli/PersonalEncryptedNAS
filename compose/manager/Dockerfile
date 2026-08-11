FROM python:3.13.7-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
RUN python -m pip install --no-cache-dir . && useradd --system --uid 10001 pnas
USER 10001:10001
ENTRYPOINT ["pnas-manager"]
