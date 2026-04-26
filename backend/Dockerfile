FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required by Playwright browsers
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		ca-certificates \
		curl \
		gnupg \
		dirmngr \
		wget \
		unzip \
		fonts-liberation \
		libnss3 \
		libgconf-2-4 \
		libatk1.0-0 \
		libatk-bridge2.0-0 \
		libcups2 \
		libx11-xcb1 \
		libxcomposite1 \
		libxdamage1 \
		libxrandr2 \
		libgbm1 \
		libasound2 \
		libxss1 \
		libpangocairo-1.0-0 \
		libgtk-3-0 \
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
