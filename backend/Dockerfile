FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install a small set of system deps; Playwright will install remaining deps with --with-deps
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		ca-certificates \
		curl \
		wget \
		unzip \
		fonts-liberation \
		libnss3 \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright and browsers
RUN pip install --no-cache-dir playwright \
	&& playwright install --with-deps

# Copy application source
COPY . /app

# Expose port (PaaS will set $PORT)
EXPOSE 8000

# Start using gunicorn; bind to $PORT if provided
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 2"]
