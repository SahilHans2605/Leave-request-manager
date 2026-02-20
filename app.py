from datetime import date, timedelta, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Team, LeaveRequest, Deadline, AuditLog
from rules import business_days, evaluate_leave

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///leave.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def log_action(actor_id: int, action: str, entity: str, entity_id: int, meta: str = ""):
    db.session.add(AuditLog(actor_user_id=actor_id, action=action, entity=entity, entity_id=entity_id, meta=meta))
    db.session.commit()

def team_size(team_id: int) -> int:
    return User.query.filter_by(team_id=team_id, role="EMPLOYEE").count()

def approved_leaves_overlapping(team_id: int, start: date, end: date) -> int:
    return (
        LeaveRequest.query
        .join(User, LeaveRequest.employee_id == User.id)
        .filter(User.team_id == team_id)
        .filter(LeaveRequest.status == "APPROVED")
        .filter(LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)
        .count()
    )

def deadline_counts(team_id: int, start: date, end: date):
    # HARD_BLOCK overlap inside leave range => instant reject
    hard_block_overlap = (
        Deadline.query
        .filter_by(team_id=team_id, policy="HARD_BLOCK")
        .filter(Deadline.date >= start, Deadline.date <= end)
        .count()
    )

    # ESCALATE overlap used for risk score
    escalate_overlap = (
        Deadline.query
        .filter_by(team_id=team_id, policy="ESCALATE")
        .filter(Deadline.date >= start, Deadline.date <= end)
        .count()
    )

    # Near-window deadlines (ESCALATE policy only), excluding overlap
    near_window_start = start - timedelta(days=3)
    near_window_end = end + timedelta(days=3)

    near_total = (
        Deadline.query
        .filter_by(team_id=team_id, policy="ESCALATE")
        .filter(Deadline.date >= near_window_start, Deadline.date <= near_window_end)
        .count()
    )
    near = max(0, near_total - escalate_overlap)

    return escalate_overlap, near, hard_block_overlap

@app.route("/")
@login_required
def home():
    if current_user.role == "MANAGER":
        return redirect(url_for("manager_dashboard"))
    return redirect(url_for("employee_leaves"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))
        login_user(user)
        return redirect(url_for("home"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/employee/leaves")
@login_required
def employee_leaves():
    if current_user.role != "EMPLOYEE":
        return redirect(url_for("home"))
    leaves = LeaveRequest.query.filter_by(employee_id=current_user.id).order_by(LeaveRequest.created_at.desc()).all()
    return render_template("employee_leaves.html", leaves=leaves)

@app.route("/employee/leave/new", methods=["GET", "POST"])
@login_required
def employee_leave_new():
    if current_user.role != "EMPLOYEE":
        return redirect(url_for("home"))

    precheck = None

    if request.method == "POST":
        start = date.fromisoformat(request.form["start_date"])
        end = date.fromisoformat(request.form["end_date"])
        leave_type = request.form.get("leave_type", "EL")
        reason = request.form.get("reason", "")

        days_req = business_days(start, end)
        t = current_user.team
        ts = team_size(t.id)
        approved_overlap = approved_leaves_overlapping(t.id, start, end)

        escalate_overlap, near_dl, hard_block_overlap = deadline_counts(t.id, start, end)

        result = evaluate_leave(
            balance=current_user.leave_balance,
            days_requested=days_req,
            team_size=ts,
            current_approved_leaves=approved_overlap,
            min_capacity=t.min_capacity,
            overlapping_deadlines=escalate_overlap,
            near_deadlines=near_dl,
            hard_block_overlaps=hard_block_overlap,
        )

        precheck = {"days_req": days_req, **result}

        if request.form.get("submit_final") == "1":
            lr = LeaveRequest(
                employee_id=current_user.id,
                start_date=start,
                end_date=end,
                leave_type=leave_type,
                reason=reason,
                risk_score=result["risk"],
                risk_level=result["level"],
            )

            if result["decision"] == "REJECT":
                lr.status = "REJECTED"
                lr.decision_note = "; ".join(result["reasons"])
                db.session.add(lr)
                db.session.commit()
                log_action(current_user.id, "SUBMIT_REJECT", "LeaveRequest", lr.id, lr.decision_note)
                flash("Request rejected by policy.", "danger")
                return redirect(url_for("employee_leaves"))

            if result["decision"] == "AUTO_APPROVE":
                lr.status = "APPROVED"
                lr.decision_note = "Auto-approved by rule engine"
                lr.decided_at = datetime.utcnow()
                current_user.leave_balance -= days_req
                db.session.add(lr)
                db.session.commit()
                log_action(current_user.id, "AUTO_APPROVE", "LeaveRequest", lr.id, f"risk={lr.risk_score}")
                flash("Leave auto-approved ✅", "success")
                return redirect(url_for("employee_leaves"))

            lr.status = "PENDING_APPROVAL"
            lr.decision_note = "Escalated to manager"
            db.session.add(lr)
            db.session.commit()
            log_action(current_user.id, "SUBMIT_ESCALATE", "LeaveRequest", lr.id, f"risk={lr.risk_score}")
            flash("Leave submitted and escalated to manager ⚠️", "warning")
            return redirect(url_for("employee_leaves"))

    return render_template("employee_leave_new.html", precheck=precheck)

@app.route("/manager/dashboard")
@login_required
def manager_dashboard():
    if current_user.role != "MANAGER":
        return redirect(url_for("home"))

    team_id = current_user.team_id

    pending = (
        LeaveRequest.query
        .join(User, LeaveRequest.employee_id == User.id)
        .filter(User.team_id == team_id)
        .filter(LeaveRequest.status == "PENDING_APPROVAL")
        .order_by(LeaveRequest.risk_score.desc())
        .all()
    )

    deadlines = (
        Deadline.query
        .filter_by(team_id=team_id)
        .order_by(Deadline.date.asc())
        .all()
    )

    ts = team_size(team_id)
    today = date.today()
    labels, capacity_values = [], []
    for i in range(7):
        d = today + timedelta(days=i)
        on_leave = (
            LeaveRequest.query
            .join(User, LeaveRequest.employee_id == User.id)
            .filter(User.team_id == team_id)
            .filter(LeaveRequest.status == "APPROVED")
            .filter(LeaveRequest.start_date <= d, LeaveRequest.end_date >= d)
            .count()
        )
        cap = (ts - on_leave) / ts if ts else 1.0
        labels.append(d.isoformat())
        capacity_values.append(round(cap * 100, 1))

    return render_template(
        "manager_dashboard.html",
        pending=pending,
        labels=labels,
        capacity_values=capacity_values,
        deadlines=deadlines
    )

@app.route("/manager/leaves/<int:leave_id>/<action>", methods=["POST"])
@login_required
def manager_decide(leave_id, action):
    if current_user.role != "MANAGER":
        return redirect(url_for("home"))

    lr = LeaveRequest.query.get_or_404(leave_id)
    emp = User.query.get(lr.employee_id)

    if lr.status != "PENDING_APPROVAL":
        flash("This request is not pending.", "info")
        return redirect(url_for("manager_dashboard"))

    if action == "approve":
        days_req = business_days(lr.start_date, lr.end_date)
        if emp.leave_balance < days_req:
            lr.status = "REJECTED"
            lr.decision_note = "Rejected: insufficient balance at decision time"
            lr.decided_by = current_user.id
            lr.decided_at = datetime.utcnow()
            db.session.commit()
            log_action(current_user.id, "REJECT", "LeaveRequest", lr.id, lr.decision_note)
            flash("Rejected due to insufficient balance.", "danger")
            return redirect(url_for("manager_dashboard"))

        lr.status = "APPROVED"
        lr.decided_by = current_user.id
        lr.decided_at = datetime.utcnow()
        lr.decision_note = "Approved by manager"
        emp.leave_balance -= days_req
        db.session.commit()
        log_action(current_user.id, "APPROVE", "LeaveRequest", lr.id, f"risk={lr.risk_score}")
        flash("Approved ✅", "success")

    elif action == "reject":
        lr.status = "REJECTED"
        lr.decided_by = current_user.id
        lr.decided_at = datetime.utcnow()
        lr.decision_note = "Rejected by manager"
        db.session.commit()
        log_action(current_user.id, "REJECT", "LeaveRequest", lr.id, f"risk={lr.risk_score}")
        flash("Rejected ❌", "warning")
    else:
        flash("Invalid action.", "danger")

    return redirect(url_for("manager_dashboard"))


# -------- Deadline CRUD (Manager) --------
@app.route("/manager/deadlines/add", methods=["POST"])
@login_required
def add_deadline():
    if current_user.role != "MANAGER":
        return redirect(url_for("home"))

    title = request.form.get("title", "").strip()
    d = request.form.get("date", "").strip()
    severity = request.form.get("severity", "MED").strip().upper()
    policy = request.form.get("policy", "ESCALATE").strip().upper()

    if not title or not d:
        flash("Title and date are required.", "danger")
        return redirect(url_for("manager_dashboard"))

    try:
        deadline_date = date.fromisoformat(d)
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("manager_dashboard"))

    if severity not in ["LOW", "MED", "HIGH", "CRIT"]:
        severity = "MED"
    if policy not in ["HARD_BLOCK", "ESCALATE"]:
        policy = "ESCALATE"

    dl = Deadline(team_id=current_user.team_id, title=title, date=deadline_date, severity=severity, policy=policy)
    db.session.add(dl)
    db.session.commit()

    log_action(current_user.id, "ADD_DEADLINE", "Deadline", dl.id, f"{title} {deadline_date} {severity} {policy}")
    flash("Deadline added ✅", "success")
    return redirect(url_for("manager_dashboard"))

@app.route("/manager/deadlines/<int:deadline_id>/edit", methods=["POST"])
@login_required
def edit_deadline(deadline_id):
    if current_user.role != "MANAGER":
        return redirect(url_for("home"))

    dl = Deadline.query.get_or_404(deadline_id)
    if dl.team_id != current_user.team_id:
        flash("Not allowed.", "danger")
        return redirect(url_for("manager_dashboard"))

    title = request.form.get("title", "").strip()
    d = request.form.get("date", "").strip()
    severity = request.form.get("severity", "MED").strip().upper()
    policy = request.form.get("policy", "ESCALATE").strip().upper()

    if not title or not d:
        flash("Title and date are required.", "danger")
        return redirect(url_for("manager_dashboard"))

    try:
        deadline_date = date.fromisoformat(d)
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("manager_dashboard"))

    if severity not in ["LOW", "MED", "HIGH", "CRIT"]:
        severity = "MED"
    if policy not in ["HARD_BLOCK", "ESCALATE"]:
        policy = "ESCALATE"

    dl.title = title
    dl.date = deadline_date
    dl.severity = severity
    dl.policy = policy
    db.session.commit()

    log_action(current_user.id, "EDIT_DEADLINE", "Deadline", dl.id, f"{title} {deadline_date} {severity} {policy}")
    flash("Deadline updated ✅", "success")
    return redirect(url_for("manager_dashboard"))

@app.route("/manager/deadlines/<int:deadline_id>/delete", methods=["POST"])
@login_required
def delete_deadline(deadline_id):
    if current_user.role != "MANAGER":
        return redirect(url_for("home"))

    dl = Deadline.query.get_or_404(deadline_id)
    if dl.team_id != current_user.team_id:
        flash("Not allowed.", "danger")
        return redirect(url_for("manager_dashboard"))

    db.session.delete(dl)
    db.session.commit()

    log_action(current_user.id, "DELETE_DEADLINE", "Deadline", deadline_id, "")
    flash("Deadline deleted 🗑️", "warning")
    return redirect(url_for("manager_dashboard"))

if __name__ == "__main__":
    app.run()