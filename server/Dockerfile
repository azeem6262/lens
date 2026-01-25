# Use the official Playwright image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set workdir
WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ONLY install Chromium (saves 500MB+ vs installing all browsers)
RUN python -m playwright install chromium

# Copy your code
COPY . .

# IMPORTANT: We use 'python -m uvicorn' to ensure the pathing is correct
# We also set --workers 1 to stay within Free Tier RAM limits
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]