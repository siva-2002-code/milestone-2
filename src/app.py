from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import csv
from flask import Response
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maintenance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

\
# Maintenance Record Model
class MaintenanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    service_type = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# Fuel Tracking & Mileage Model
class FuelRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    mileage = db.Column(db.Float, nullable=False)
    fuel_cost = db.Column(db.Float, nullable=False)
    fuel_amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home Route
@app.route("/")
def home():
    return render_template("home.html")

# Register Route
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully!", "success")
        return redirect(url_for('login'))

    return render_template("register.html")

# Login Route
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Login unsuccessful. Check your email and password.", "danger")

    return render_template("login.html")

# Logout Route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# Dashboard Route
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

# Add Maintenance Service with Reminder Date
@app.route("/add_service", methods=['GET', 'POST'])
@login_required
def add_service():
    if request.method == 'POST':
        service_type = request.form['service_type']
        cost = request.form['cost']
        notes = request.form['notes']

        new_record = MaintenanceRecord(
            service_type=service_type, 
            cost=float(cost), 
            notes=notes, 
            user_id=current_user.id
        )
        db.session.add(new_record)
        db.session.commit()
        flash("Maintenance record added!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_service.html")


# View & Search Services
@app.route("/view_services", methods=['GET', 'POST'])
@login_required
def view_services():
    query = MaintenanceRecord.query.filter_by(user_id=current_user.id)

    if request.method == 'POST':
        service_type = request.form.get("service_type")
        min_cost = request.form.get("min_cost")
        max_cost = request.form.get("max_cost")

        if service_type:
            query = query.filter(MaintenanceRecord.service_type.ilike(f"%{service_type}%"))
        if min_cost:
            query = query.filter(MaintenanceRecord.cost >= float(min_cost))
        if max_cost:
            query = query.filter(MaintenanceRecord.cost <= float(max_cost))

    records = query.order_by(MaintenanceRecord.date.desc()).all()
    return render_template("view_services.html", records=records)

# Add Fuel Tracking
@app.route("/add_fuel", methods=['GET', 'POST'])
@login_required
def add_fuel():
    if request.method == 'POST':
        mileage = request.form['mileage']
        fuel_cost = request.form['fuel_cost']
        fuel_amount = request.form['fuel_amount']

        new_fuel_record = FuelRecord(
            mileage=float(mileage),
            fuel_cost=float(fuel_cost),
            fuel_amount=float(fuel_amount),
            user_id=current_user.id
        )
        db.session.add(new_fuel_record)
        db.session.commit()
        flash("Fuel record added!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_fuel.html")

# View Fuel Logs
@app.route("/view_fuel")
@login_required
def view_fuel():
    fuel_records = FuelRecord.query.filter_by(user_id=current_user.id).order_by(FuelRecord.date.desc()).all()
    return render_template("view_fuel.html", records=fuel_records)


# View Reports Route
@app.route("/view_reports")
@login_required
def view_reports():
    maintenance_count = MaintenanceRecord.query.filter_by(user_id=current_user.id).count()
    total_maintenance_cost = db.session.query(db.func.sum(MaintenanceRecord.cost)).filter_by(user_id=current_user.id).scalar() or 0
    total_fuel_spent = db.session.query(db.func.sum(FuelRecord.fuel_cost)).filter_by(user_id=current_user.id).scalar() or 0
    total_fuel_liters = db.session.query(db.func.sum(FuelRecord.fuel_amount)).filter_by(user_id=current_user.id).scalar() or 0
    avg_fuel_efficiency = db.session.query(db.func.avg(FuelRecord.mileage)).filter_by(user_id=current_user.id).scalar() or 0

    return render_template("view_reports.html", 
        maintenance_count=maintenance_count, 
        total_maintenance_cost=total_maintenance_cost,
        total_fuel_spent=total_fuel_spent,
        total_fuel_liters=total_fuel_liters,
        avg_fuel_efficiency=avg_fuel_efficiency
    )

# Settings Route
@app.route("/settings", methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        theme = request.form.get("theme")
        currency = request.form.get("currency")
        notifications = request.form.get("notifications") == "on"

        flash("Settings updated successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("settings.html")

@app.route("/export_service_history")
@login_required
def export_service_history():
    """Exports the user's service history as a CSV file."""
    
    # Create an in-memory stream for CSV data
    stream = io.StringIO()
    writer = csv.writer(stream)
    
    # Write the CSV header
    writer.writerow(["Date", "Service Type", "Cost", "Notes"])
    
    # Query the database for user's service history
    records = MaintenanceRecord.query.filter_by(user_id=current_user.id).order_by(MaintenanceRecord.date.desc()).all()
    
    # Write the records to the CSV
    for record in records:
        writer.writerow([record.date, record.service_type, record.cost, record.notes])
    
    # Prepare response
    response = Response(stream.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=service_history.csv"
    
    return response


# Initialize Database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
