import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# -----------------------------------------------------------------------
# Database configuration
# Set DATABASE_URL to a PostgreSQL DSN for production (e.g. on Azure):
#   postgresql+psycopg2://user:pass@host/dbname
# Defaults to local SQLite file for development.
# -----------------------------------------------------------------------
_default_db = "sqlite:///" + os.path.join(os.path.dirname(__file__), "applications.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", _default_db)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    application_number = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), nullable=False)
    current_status = db.Column(db.String(100), nullable=False)
    next_action = db.Column(db.String(100), nullable=False)
    next_action_due_date = db.Column(db.String(20), nullable=False)
    last_updated = db.Column(db.String(20), nullable=False)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self):
        return {
            "id": self.id,
            "application_number": self.application_number,
            "company": self.company,
            "role": self.role,
            "current_status": self.current_status,
            "next_action": self.next_action,
            "next_action_due_date": self.next_action_due_date,
            "last_updated": self.last_updated,
        }


def init_db():
    with app.app_context():
        db.create_all()


# Run schema init at import time so gunicorn (production) and the dev server
# both auto-create tables without any manual step.
init_db()


STATUS_OPTIONS = [
    "Applied",
    "Phone Screen",
    "Interview Scheduled",
    "Offer Received",
    "Rejected",
    "Withdrawn",
]

NEXT_ACTION_OPTIONS = [
    "Follow Up",
    "Prepare for Interview",
    "Send Thank You",
    "Await Decision",
    "None",
]


def _validate_form(form):
    """Return list of error strings; empty list means valid."""
    errors = []
    if not form.get("application_number", "").strip():
        errors.append("Application Number is required.")
    if not form.get("company", "").strip():
        errors.append("Company is required.")
    if not form.get("role", "").strip():
        errors.append("Role is required.")
    if not form.get("current_status", "").strip():
        errors.append("Current Status is required.")
    if not form.get("next_action", "").strip():
        errors.append("Next Action is required.")
    if not form.get("next_action_due_date", "").strip():
        errors.append("Next Action Due Date is required.")
    if not form.get("last_updated", "").strip():
        errors.append("Last Updated date is required.")
    return errors


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/applications")
def applications():
    apps = Application.query.order_by(Application.last_updated.desc()).all()
    return render_template("applications.html", applications=apps)


@app.route("/applications/new", methods=["GET", "POST"])
def add_entry():
    if request.method == "POST":
        errors = _validate_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "add_entry.html",
                status_options=STATUS_OPTIONS,
                next_action_options=NEXT_ACTION_OPTIONS,
                form_data=request.form,
            )

        app_entry = Application(
            application_number=request.form["application_number"].strip(),
            company=request.form["company"].strip(),
            role=request.form["role"].strip(),
            current_status=request.form["current_status"].strip(),
            next_action=request.form["next_action"].strip(),
            next_action_due_date=request.form["next_action_due_date"].strip(),
            last_updated=request.form["last_updated"].strip(),
        )
        db.session.add(app_entry)
        db.session.commit()
        flash("Application added successfully!", "success")
        return redirect(url_for("applications"))

    return render_template(
        "add_entry.html",
        status_options=STATUS_OPTIONS,
        next_action_options=NEXT_ACTION_OPTIONS,
        form_data={},
    )


@app.route("/applications/<int:app_id>")
def application_detail(app_id):
    application = Application.query.get_or_404(app_id)
    return render_template(
        "details.html",
        application=application,
        status_options=STATUS_OPTIONS,
        next_action_options=NEXT_ACTION_OPTIONS,
    )


@app.route("/applications/<int:app_id>/edit", methods=["POST"])
def edit_application(app_id):
    application = Application.query.get_or_404(app_id)

    errors = _validate_form(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
        return render_template(
            "details.html",
            application=application,
            status_options=STATUS_OPTIONS,
            next_action_options=NEXT_ACTION_OPTIONS,
        )

    application.application_number = request.form["application_number"].strip()
    application.company = request.form["company"].strip()
    application.role = request.form["role"].strip()
    application.current_status = request.form["current_status"].strip()
    application.next_action = request.form["next_action"].strip()
    application.next_action_due_date = request.form["next_action_due_date"].strip()
    application.last_updated = request.form["last_updated"].strip()
    db.session.commit()

    flash("Application updated successfully!", "success")
    return redirect(url_for("application_detail", app_id=app_id))


@app.route("/applications/<int:app_id>/delete", methods=["POST"])
def delete_application(app_id):
    application = Application.query.get_or_404(app_id)
    db.session.delete(application)
    db.session.commit()
    flash("Application deleted.", "info")
    return redirect(url_for("applications"))


@app.route("/next-actions")
def next_actions():
    return render_template("next_actions.html")


@app.route("/next-actions/upcoming")
def upcoming_actions():
    today = date.today().isoformat()
    apps = (
        Application.query
        .filter(
            Application.next_action_due_date >= today,
            Application.next_action != "None",
        )
        .order_by(Application.next_action_due_date.asc())
        .all()
    )
    return render_template("upcoming_actions.html", applications=apps, today=today)


@app.route("/next-actions/overdue")
def overdue_actions():
    today = date.today().isoformat()
    apps = (
        Application.query
        .filter(
            Application.next_action_due_date < today,
            Application.next_action != "None",
        )
        .order_by(Application.next_action_due_date.asc())
        .all()
    )
    return render_template("overdue_actions.html", applications=apps, today=today)


@app.route("/weekly-review")
def weekly_review():
    today = date.today().isoformat()
    upcoming = (
        Application.query
        .filter(
            Application.next_action_due_date >= today,
            Application.next_action != "None",
        )
        .order_by(Application.next_action_due_date.asc())
        .all()
    )
    overdue = (
        Application.query
        .filter(
            Application.next_action_due_date < today,
            Application.next_action != "None",
        )
        .order_by(Application.next_action_due_date.asc())
        .all()
    )
    return render_template("weekly_review.html", upcoming=upcoming, overdue=overdue, today=today)


@app.route("/status-history")
def status_history():
    apps = Application.query.order_by(Application.last_updated.desc()).all()
    status_counts = {}
    for a in apps:
        status_counts[a.current_status] = status_counts.get(a.current_status, 0) + 1
    return render_template("status_history.html", applications=apps, status_counts=status_counts)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
