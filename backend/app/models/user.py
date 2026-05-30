"""User model for CSUF Scheduler."""

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

try:
    from ..database import db
except (ImportError, ModuleNotFoundError):
    from database import db


class User(db.Model):
    """Represents a user (student, admin, etc.)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False, default="student")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        # Prefer first/last name when available
        if self.first_name or self.last_name:
            display = f"{self.first_name or ''} {self.last_name or ''}".strip()
        else:
            display = self.name or ""
        return {
            "id": self.id,
            "name": display,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "role": self.role,
        }

    def set_password(self, password: str):
        if password:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
