FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY services ./services
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "services.content.main:app", "--host", "0.0.0.0", "--port", "8000"]
