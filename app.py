import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, g
import uuid
import os

# --- 0. GLOBAL CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'DEMO_KEY_SIMPLE_ROUTING_12345' 
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
DATABASE = 'orders.db'


# --- 1. HELPER FUNCTIONS & DB MANAGEMENT ---

def get_db():
    """Returns a new database connection or the existing one."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        # Use Row objects to access columns by name (like a dictionary)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initializes the database schema."""
    try:
        with app.app_context():
            db = get_db()
            # Ensure the schema.sql file exists and is readable
            if not os.path.exists('schema.sql'):
                print("ERROR: schema.sql file not found. Database setup failed.")
                return False
            
            with app.open_resource('schema.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()
            print("Database initialized successfully.")
            return True
    except Exception as e:
        print(f"FATAL ERROR during DB initialization: {e}")
        return False

@app.route('/init_db')
def init_db_route():
    """A route to manually initialize the database."""
    if init_db():
        return "Database initialized! Go back to the <a href='/'>homepage</a>."
    else:
        return "Failed to initialize database. Check console for errors and ensure schema.sql exists."

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- DYNAMIC PRICING LOGIC ---

def calculate_estimated_quote(project_type, description, timeline):
    """
    Calculates a dynamic quote based on project type, description complexity, and timeline.
    """
    base_price = 0

    # Base pricing by project type
    if project_type == 'website':
        base_price = 8000
    elif project_type == 'software':
        base_price = 15000
    elif project_type == 'it_solution':
        base_price = 5000
    elif project_type == 'consultation':
        base_price = 2000
    else:
        # Fallback price
        base_price = 7500 
    
    # Complexity modifier: increase price for detailed or large scopes
    if len(description) > 500:
        base_price *= 1.25 # 25% premium for complex projects
    elif len(description) > 250:
        base_price *= 1.10 # 10% premium for medium complexity

    # Timeline modifier (Rush fee)
    if "urgent" in (timeline or "").lower():
        base_price += 1500 # Rush fee
    
    # Round up to the nearest $500 for cleaner estimates
    return round(base_price / 500) * 500


# --- 2. BEFORE REQUEST (Global Context) ---

@app.before_request
def before_request():
    """Sets up a mock translation object (g.T) for clean templating."""
    g.T = {
        'home': 'Home',
        'services': 'Services',
        'about': 'About Us',
        'contact': 'Contact',
        'order': 'Get a Quote',
        # Payment strings for the payment.html template
        'payment_title': 'Project Confirmation & Payment',
        'payment_subtitle': 'Review your project details and select a payment method.',
        'summary_title': 'Your Project Brief',
        'order_id': 'Confirmation ID:',
        'email_label': 'Client Email:',
        'client': 'Project Type:',
        'total_amount': 'Quote Amount:',
        'button_complete_pay': 'Complete Payment',
        'payment_note': 'Note: This is a DEMO payment process. Your data is saved locally in SQLite.',
    }


# --- 3. ROUTE DEFINITIONS ---

@app.route('/')
def index():
    # Placeholder for a real homepage
    return render_template('index.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash('Thank you for reaching out! We will be in touch shortly.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


@app.route('/order', methods=['GET', 'POST'])
def order_briefing():
    """
    Handles the order form submission, calculates dynamic quote, saves data to SQLite,
    and redirects to the dynamic payment route.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        project_type_raw = request.form.get('project_type')
        budget = request.form.get('budget') # New field collected
        timeline = request.form.get('timeline') # New field collected
        description = request.form.get('description')
        
        # Simple validation
        if not all([email, project_type_raw, description]):
            flash('Validation Error: Please fill out all required fields (Email, Type, Description).', 'danger')
            return render_template('order.html', form_data=request.form) 

        # 1. Generate dynamic data
        order_key = str(uuid.uuid4())[:8].upper() 
        # *** CORRECTED: Use dynamic quote function ***
        calculated_quote = calculate_estimated_quote(project_type_raw, description, timeline)
        
        try:
            # 2. Save to SQLite (*** CORRECTED: Added budget and timeline to INSERT ***)
            db = get_db()
            db.execute("""
                INSERT INTO orders (order_id, project_type, client_email, description, quote, status, budget, timeline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_key, project_type_raw.replace('_', ' ').title(), email, description, calculated_quote, 'PENDING', budget, timeline))
            db.commit()
            
            flash(f'Order Brief Submitted! Your quote is ${calculated_quote}. Proceeding to payment confirmation.', 'success')
            
            # 3. Redirect with the dynamic order ID
            return redirect(url_for('handle_payment_route', order_id=order_key))
            
        except sqlite3.OperationalError as e:
            flash(f'Database Error: Could not save order. Did you run /init_db with the correct schema? Error: {e}', 'danger')
            return render_template('order.html', form_data=request.form)

    return render_template('order.html')


@app.route('/payment/<order_id>', methods=['GET', 'POST'])
def handle_payment_route(order_id):
    """
    Renders the payment summary page by fetching data from SQLite based on the URL parameter.
    Also handles the POST request for mock payment confirmation.
    """
    db = get_db()
    
    # 1. Fetch Order Data from SQLite
    # Fetch all relevant columns, including budget and timeline
    cursor = db.execute("""
        SELECT order_id, project_type, client_email, description, quote, status, budget, timeline 
        FROM orders WHERE order_id = ?
    """, (order_id,))
    order_data = cursor.fetchone() 
    
    if not order_data:
        flash(f'Error: Order ID {order_id} not found in the system.', 'danger')
        return redirect(url_for('order_briefing'))

    if request.method == 'POST':
        payment_method = request.form.get('payment_method', 'N/A')
        
        # 2. Update Status (Mock Payment)
        db.execute("UPDATE orders SET status = ?, payment_method = ? WHERE order_id = ?", 
                   ('PAID', payment_method, order_id))
        db.commit()
        
        flash(f'Order ID {order_id} confirmed! Payment via {payment_method.capitalize()} is processing (DEMO). Thank you!', 'success')
        return redirect(url_for('index'))

    # 3. Render Page with actual order data
    return render_template('payment.html', order=order_data, order_id=order_id)


# --- 4. RUN THE APP ---
if __name__ == '__main__':
    # Initial check to suggest initialization if the DB file is missing
    if not os.path.exists(DATABASE):
        print(f"\n--- WARNING ---")
        print(f"Database file '{DATABASE}' not found. Please navigate to /init_db once in your browser.")
        print(f"---------------\n")

    app.run(debug=True)
