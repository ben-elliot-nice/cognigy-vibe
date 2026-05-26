FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml .
COPY cognigy_mcp/ cognigy_mcp/

RUN uv pip install --system .

ENV PORT=8080
EXPOSE 8080

CMD ["cognigy-vibe-mcp-server"]
