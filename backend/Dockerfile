FROM mcr.microsoft.com/playwright/python:1.40.0-focal

# Set working directory
WORKDIR /app

# Copy only requirements first to leverage caching
COPY requirements.txt ./

# Install python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy app sources
COPY . /app

# Expose port (Render will set $PORT)
EXPOSE 8000

# Use gunicorn to serve the Flask app; bind to port 8000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "2"]
