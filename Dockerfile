# Dockerfile voor Braster-Empire Bot
FROM python:3.11-slim

# Zorg dat Python niet buffert (handig voor logs)
ENV PYTHONUNBUFFERED=1

# Werkdirectory in de container
WORKDIR /app

# Vereisten installeren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy alle bestanden
COPY . .

# Start de bot
CMD ["python", "bot.py"]
