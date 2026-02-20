from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Team(db.Model):
    __tablename__ = "teams"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    min_capacity = db.Column(db.Float, default=0.60)  # 60%

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False)  # EMPLOYEE / MANAGER
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    team = db.relationship("Team")

    leave_balance = db.Column(db.Float, default=12.0)  # days (employees only)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

class Deadline(db.Model):
    __tablename__ = "deadlines"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    team = db.relationship("Team")
    title = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False)
    severity = db.Column(db.String(10), default="MED")  # LOW/MED/HIGH/CRIT

class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"
    id = db.Column(db.Integer, primary_key=True)

    employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    employee = db.relationship("User", foreign_keys=[employee_id])

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(10), default="EL")  # EL/CL/SL
    reason = db.Column(db.String(255), default="")

    status = db.Column(db.String(20), default="SUBMITTED")
    risk_score = db.Column(db.Integer, default=0)
    risk_level = db.Column(db.String(10), default="LOW")  # LOW/MED/HIGH
    decision_note = db.Column(db.String(255), default="")

    decided_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)  # SUBMIT/AUTO_APPROVE/APPROVE/REJECT
    entity = db.Column(db.String(50), nullable=False)  # LeaveRequest
    entity_id = db.Column(db.Integer, nullable=False)
    meta = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
