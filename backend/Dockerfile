FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ORTOOLS_NUM_SEARCH_WORKERS=1
ENV ORTOOLS_MAX_TIME_SECONDS=12

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# copy application (build context is backend/)
COPY . /app/

# default port
ENV PORT=5000

EXPOSE 5000

# Run as unprivileged user
RUN useradd -m appuser
USER appuser

CMD ["gunicorn", "wsgi:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120"]
