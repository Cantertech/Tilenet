# Use more secure base image
FROM python:3.13-slim

# Install WeasyPrint dependencies and system libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    pkg-config \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    gtk-update-icon-cache \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy code
COPY . .

RUN python3.13 -m venv /app/venv && \
    . /app/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose app port
EXPOSE 8000
RUN . /app/venv/bin/activate && python manage.py collectstatic --noinput

CMD ["/app/venv/bin/gunicorn", "tile_estimator.wsgi:application", "--bind", "0.0.0.0:8000", "--log-level", "debug", "--error-logfile", "-", "--access-logfile", "-"]
