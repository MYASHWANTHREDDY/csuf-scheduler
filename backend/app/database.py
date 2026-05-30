"""Database extension holder.

Expose `db = SQLAlchemy()` for application modules to import and use.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
