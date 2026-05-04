FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_project ./mcp_project
COPY schema.sql ./schema.sql

EXPOSE 8000

CMD ["python", "mcp_project/server.py", "--transport", "sse", "--port", "8000"]
