# Dockerfile voor Braster‑Empire Bot
FROM python:3.11-slim

# Python niet bufferen (betere logs)
ENV PYTHONUNBUFFERED=1

# Werkdirectory in de container
WORKDIR /app

# Vereisten installeren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy alle projectbestanden
COPY . .

# Start de bot
CMD ["python", "bot.py"]