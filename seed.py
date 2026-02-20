from datetime import date, timedelta
from app import app
from models import db, Team, User, Deadline

def run():
    with app.app_context():
        db.drop_all()
        db.create_all()

        team = Team(name="Engineering Alpha", min_capacity=0.60)
        db.session.add(team)
        db.session.commit()

        mgr = User(full_name="Rahul Verma", email="manager@demo.com", role="MANAGER", team_id=team.id, leave_balance=0)
        mgr.set_password("demo123")
        db.session.add(mgr)

        employees = []
        for i in range(1, 6):
            u = User(full_name=f"Employee {i}", email=f"e{i}@demo.com", role="EMPLOYEE", team_id=team.id, leave_balance=12)
            u.set_password("demo123")
            employees.append(u)
        db.session.add_all(employees)

        # Add a couple deadlines to create conflict scenarios
        db.session.add(Deadline(team_id=team.id, title="Sprint End", date=date.today() + timedelta(days=3), severity="HIGH"))
        db.session.add(Deadline(team_id=team.id, title="Release v1", date=date.today() + timedelta(days=7), severity="MED"))

        db.session.commit()

        print("✅ Seed complete.")
        print("Manager login: manager@demo.com / demo123")
        print("Employee login: e1@demo.com / demo123 (also e2..e5)")

if __name__ == "__main__":
    run()
