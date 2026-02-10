from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class BiosReference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(50))
    model_name = db.Column(db.String(100), unique=True)
    latest_version = db.Column(db.String(50))
    last_checked = db.Column(db.DateTime, default=datetime.now)
    # Flaga "Brak wsparcia / OLD"
    is_old = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'vendor': self.vendor,
            'model_name': self.model_name,
            'latest_version': self.latest_version,
            'is_old': self.is_old
        }