FROM python:3.13.2-slim

WORKDIR /app

# Install system dependencies
#RUN apt-get update && apt-get install -y \
#    git \
#    build-essential \
#    python3-dev \
#    wget \
#    && apt-get clean \
#    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]