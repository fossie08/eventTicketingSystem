import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# === Helper Functions ===
def load_data(filename):
    """Load JSON data from a file."""
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return json.load(f)


def save_data(filename, data):
    """Save data to a JSON file."""
    path = os.path.join(BASE_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def get_user_by_email(email):
    """Return a user dictionary from users.json that matches the given email."""
    users = load_data('users.json')
    for user in users:
        if user.get('email') == email:
            return user
    return None


# === Decorators ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Admin access required.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# === User Routes ===

@app.route('/')
def index():
    """User homepage: list upcoming events."""
    events = load_data('events.json')
    # Assign an id (based on index) to each event for linking purposes.
    for i, event in enumerate(events):
        event['id'] = i
    return render_template('user/index.html', events=events)


@app.route('/event/<int:event_id>')
def event_detail(event_id):
    """Display the details for a single event."""
    events = load_data('events.json')
    if event_id < 0 or event_id >= len(events):
        flash("Event not found.", "danger")
        return redirect(url_for('index'))
    event = events[event_id]
    event['id'] = event_id
    return render_template('user/event_detail.html', event=event)


@app.route('/purchase_ticket/<int:event_id>', methods=['GET', 'POST'])
@login_required
def purchase_ticket(event_id):
    """Display and process the purchase ticket form for a given event."""
    events = load_data('events.json')
    if event_id < 0 or event_id >= len(events):
        flash("Event not found.", "danger")
        return redirect(url_for('index'))
    event = events[event_id]
    event['id'] = event_id
    if request.method == 'POST':
        try:
            quantity = int(request.form.get('quantity', 1))
        except ValueError:
            quantity = 1
        ticket_price = 50  # Assume a fixed price per ticket for demonstration
        event['tickets_sold'] = event.get('tickets_sold', 0) + quantity
        event['revenue'] = event.get('revenue', 0) + (quantity * ticket_price)
        save_data('events.json', events)
        # Record the activity
        activities = load_data('activity.json')
        user = session.get('user')
        activities.append({
            "user": user.get('username'),
            "activity": f"Purchased {quantity} ticket(s) for {event.get('name')}",
            "date": "2023-10-01"  # In a real app, use the current date/time
        })
        save_data('activity.json', activities)
        flash("Ticket purchase successful!", "success")
        return redirect(url_for('account'))
    return render_template('user/purchase_ticket.html', event=event)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login (also used for admin login)."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # Check for admin login (hard-coded credentials for demonstration)
        if email == "admin@example.com" and password == "admin":
            session['user'] = {"username": "Admin", "email": email}
            session['is_admin'] = True
            flash("Logged in as admin.", "success")
            return redirect(url_for('admin_dashboard'))
        # Check for regular user
        user = get_user_by_email(email)
        if user and user.get('password') == password:
            session['user'] = user
            session['is_admin'] = user.get('is_admin', False)
            flash("Logged in successfully.", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login'))
    return render_template('user/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        users = load_data('users.json')
        if any(u.get('email') == email for u in users):
            flash("Email already registered.", "warning")
            return redirect(url_for('register'))
        new_user = {"username": username, "email": email, "password": password, "is_admin": False}
        users.append(new_user)
        save_data('users.json', users)
        session['user'] = new_user
        session['is_admin'] = False
        flash("Registration successful.", "success")
        return redirect(url_for('index'))
    return render_template('user/register.html')


@app.route('/account')
@login_required
def account():
    """User account page."""
    current_user = session.get('user')
    return render_template('user/account.html', current_user=current_user)


@app.route('/edit_account', methods=['GET', 'POST'])
@login_required
def edit_account():
    """Allow the user to edit their account (currently, just the username)."""
    current_user = session.get('user')
    if request.method == 'POST':
        username = request.form.get('username')
        users = load_data('users.json')
        for user in users:
            if user.get('email') == current_user.get('email'):
                user['username'] = username
                current_user['username'] = username
                break
        save_data('users.json', users)
        session['user'] = current_user
        flash("Account updated successfully.", "success")
        return redirect(url_for('account'))
    return render_template('user/edit_account.html', current_user=current_user)


@app.route('/logout')
def logout():
    """Logout the current user (admin or regular user)."""
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('index'))


# === Admin Routes ===

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard displaying summary statistics, recent events, and user activity."""
    events = load_data('events.json')
    users = load_data('users.json')
    activities = load_data('activity.json')
    total_events = len(events)
    total_users = len(users)
    total_revenue = sum(event.get('revenue', 0) for event in events)
    event_attendance = "75%"  # This value could be calculated dynamically
    recent_events = sorted(events, key=lambda x: x.get('date', ''), reverse=True)
    user_activities = sorted(activities, key=lambda x: x.get('date', ''), reverse=True)
    return render_template('admin/dashboard.html',
                           total_events=total_events,
                           total_users=total_users,
                           total_revenue=total_revenue,
                           event_attendance=event_attendance,
                           recent_events=recent_events,
                           user_activities=user_activities)


@app.route('/admin/events')
@admin_required
def admin_events():
    """List all events for admin management."""
    events = load_data('events.json')
    for i, event in enumerate(events):
        event['id'] = i
    return render_template('admin/events.html', events=events)


@app.route('/admin/add_event', methods=['GET', 'POST'])
@admin_required
def add_event():
    """Add a new event."""
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        location = request.form.get('location')
        try:
            tickets_sold = int(request.form.get('tickets_sold', 0))
        except ValueError:
            tickets_sold = 0
        try:
            revenue = float(request.form.get('revenue', 0))
        except ValueError:
            revenue = 0.0
        new_event = {
            "name": name,
            "date": date,
            "location": location,
            "tickets_sold": tickets_sold,
            "revenue": revenue
        }
        events = load_data('events.json')
        events.append(new_event)
        save_data('events.json', events)
        flash("Event added successfully.", "success")
        return redirect(url_for('admin_events'))
    return render_template('admin/add_event.html')


@app.route('/admin/edit_event/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    """Edit an existing event."""
    events = load_data('events.json')
    if event_id < 0 or event_id >= len(events):
        flash("Event not found.", "danger")
        return redirect(url_for('admin_events'))
    event = events[event_id]
    if request.method == 'POST':
        event['name'] = request.form.get('name')
        event['date'] = request.form.get('date')
        event['location'] = request.form.get('location')
        try:
            event['tickets_sold'] = int(request.form.get('tickets_sold', event.get('tickets_sold', 0)))
        except ValueError:
            event['tickets_sold'] = event.get('tickets_sold', 0)
        try:
            event['revenue'] = float(request.form.get('revenue', event.get('revenue', 0)))
        except ValueError:
            event['revenue'] = event.get('revenue', 0)
        events[event_id] = event
        save_data('events.json', events)
        flash("Event updated successfully.", "success")
        return redirect(url_for('admin_events'))
    event['id'] = event_id
    return render_template('admin/edit_event.html', event=event)


@app.route('/admin/delete_event/<int:event_id>')
@admin_required
def delete_event(event_id):
    """Delete an event."""
    events = load_data('events.json')
    if event_id < 0 or event_id >= len(events):
        flash("Event not found.", "danger")
    else:
        events.pop(event_id)
        save_data('events.json', events)
        flash("Event deleted successfully.", "success")
    return redirect(url_for('admin_events'))


@app.route('/admin/users')
@admin_required
def admin_users():
    """List all users for admin management."""
    users = load_data('users.json')
    for i, user in enumerate(users):
        user['id'] = i
    return render_template('admin/users.html', users=users)


@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit a user’s details."""
    users = load_data('users.json')
    if user_id < 0 or user_id >= len(users):
        flash("User not found.", "danger")
        return redirect(url_for('admin_users'))
    user = users[user_id]
    if request.method == 'POST':
        user['username'] = request.form.get('username')
        user['email'] = request.form.get('email')
        users[user_id] = user
        save_data('users.json', users)
        flash("User updated successfully.", "success")
        return redirect(url_for('admin_users'))
    user['id'] = user_id
    return render_template('admin/edit_user.html', user=user)


@app.route('/admin/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    """Delete a user."""
    users = load_data('users.json')
    if user_id < 0 or user_id >= len(users):
        flash("User not found.", "danger")
    else:
        users.pop(user_id)
        save_data('users.json', users)
        flash("User deleted successfully.", "success")
    return redirect(url_for('admin_users'))


@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    """A placeholder for admin analytics."""
    return render_template('admin/analytics.html')


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Display and update admin settings."""
    settings_file = os.path.join(BASE_DIR, 'settings.json')
    settings = {}
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings = json.load(f)
    if request.method == 'POST':
        site_name = request.form.get('site_name')
        settings['site_name'] = site_name
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        flash("Settings updated successfully.", "success")
        return redirect(url_for('admin_settings'))
    return render_template('admin/settings.html', settings=settings)


# === Run the Application ===
if __name__ == '__main__':
    app.run(debug=True)
