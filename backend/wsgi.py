"""WSGI entrypoint for Gunicorn.

Gunicorn can be started with:
  gunicorn --bind 0.0.0.0:5000 wsgi:app

This imports the app factory and creates the app using current environment.
"""

"""Robust WSGI entrypoint that supports running from different working directories
and bind-mounted `backend` content (dev Docker override).

It attempts imports in order that covers these layouts:
- when package is installed/used as `backend` package: import backend.app
- when running with the backend folder mounted as /app (package name `app`): use relative import
- fallback to absolute import from `app` module if available.
"""
try:
    # Preferred: when running as package (repo root), import backend.app
    from backend.app import create_app
except (ImportError, ModuleNotFoundError):
    try:
        # If this file is executed inside a package at /app where app.py is adjacent,
        # use a relative import to load the app factory from app.py
        from .app import create_app
    except (ImportError, ModuleNotFoundError):
        # Final fallback: try absolute import of app module
        from app import create_app

app = create_app()
