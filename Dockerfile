# Start from an official, slim Python image
FROM python:3.13-slim

WORKDIR /app

# Install packages first, so Docker can reuse this layer when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code
COPY . .

# Build all the data inside the image (takes several minutes)
RUN python build_all.py

# Hosting services set PORT; default to 8000 on your Mac
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]