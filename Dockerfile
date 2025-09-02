# Kleine, schone Python base
FROM python:3.12-slim

# Sneller/kleiner en geen versie-check spam
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Werkmap
WORKDIR /app

# Maak dedicated virtualenv zodat pip geen systeem-packages raakt
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# (Optioneel maar netjes) run als niet-root
RUN adduser --disabled-password --gecos "" app
USER app

# Dependencies eerst kopiëren en installeren (betere Docker cache)
COPY --chown=app:app requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Dan pas de rest van de code
COPY --chown=app:app . .

# Start je bot (pas aan als jouw entrypoint anders heet)
CMD ["python", "bot.py"]