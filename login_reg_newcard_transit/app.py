from flask import Flask, render_template, request, redirect, url_for, session , jsonify
import pyodbc
import re
from passlib.hash import pbkdf2_sha256
import secrets
from datetime import datetime, timedelta
import calendar



app = Flask(__name__)

# Generate a random secret key
app.secret_key = secrets.token_hex(16)

# connection string for mta_db
conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=LAPTOP-93PFC6D0\SQLEXPRESS;DATABASE=mta_db;UID=admin;PWD=admin'
conn = pyodbc.connect(conn_str)

cursor = conn.cursor()


#validating  registration
def is_valid_name(name):
    return len(name) >= 2 and name.isalpha()

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def format_phone(phone):
    # Formating the phone number as +1 (XXX) XXX-XXXX
    return f'+1 ({phone[:3]}) {phone[3:6]}-{phone[6:]}'

def is_valid_phone(phone):
    #  phone number formats: (XXX) XXX-XXXX or XXX-XXX-XXXX
    pattern = r'^\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})$'
    return re.match(pattern, phone) is not None

def is_email_unique(email):
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_email = ?", (email,))
    count = cursor.fetchone()[0]
    return count == 0

def is_strong_password(password):
    # Enforce a strong password policy
    # Minimum length: 8 characters
    # At least one uppercase letter
    # At least one lowercase letter
    # At least one digit
    # At least one special character
    return (
        len(password) >= 8 and
        any(char.isupper() for char in password) and
        any(char.islower() for char in password) and
        any(char.isdigit() for char in password) and
        any(char in '!@#$%^&*()-_=+[]{}|;:\'",.<>/?' for char in password)
    )



# REGISTRATION
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        #username = request.form['username']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        

        # Check if passwords match
        if password != confirm_password:
            return "Passwords do not match. Please try again."

        # Validate first_name and last_name
        if not is_valid_name(first_name) or not is_valid_name(last_name):
            return "Invalid first name or last name format. Please check and try again."

        # Validate email
        if not is_valid_email(email):
            return "Invalid email format. Please enter a valid email address."

        # Validate phone number
        if not is_valid_phone(phone_number):
            return "Invalid phone number format. Please enter a valid Canadian phone number."

        # Format phone number
        formatted_phone = format_phone(phone_number)

        # Check email uniqueness
        if not is_email_unique(email):
            return "Email already exists. Please use a different email address."

        # Check strong password policy
        if not is_strong_password(password):
            return "Password does not meet the strong password policy. Please try again."

        # Hash the password using passlib
        hashed_password = pbkdf2_sha256.hash(password)

        # Use parameterized queries to prevent SQL injection
        cursor.execute('''
            INSERT INTO users ( user_password, user_email, user_phn_no, first_name, last_name)
            VALUES ( ?, ?, ?, ?, ?)
        ''', ( hashed_password, email, formatted_phone, first_name, last_name))

        conn.commit()
        return redirect(url_for('welcome'))

    return render_template('register.html')

# REGISTRATION SUCCESS
@app.route('/registration_success')
def registration_success():
    return "Registration successful!"



# LOGIN
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_email = request.form['username_email']
        password = request.form['password']

        # Query the database to check if the username or email exists
        cursor.execute("SELECT * FROM users WHERE user_email = ?", (username_email,))

        user = cursor.fetchone()

        if user and pbkdf2_sha256.verify(password, user.user_password):
            # Login successful, store user ID in session
            session['user_id'] = user.user_id  # Assuming 'user_id' is the correct column name
            return redirect(url_for('welcome'))

        else:
            return "Invalid login credentials. Please try again."

    return render_template('login.html', register_url=url_for('register'))




# WELCOME PAGE
@app.route('/welcome', methods=['GET', 'POST'])
def welcome():
    if request.method == 'POST':
        # Handle transit selection
        selected_transit = request.form.get('transit_select')
        if selected_transit:
            # Redirect to the selected transit page
            return redirect(url_for('transit', transit_name=selected_transit))

        # Handle logout request
        if 'log_out' in request.form:
            session.pop('user_id', None)  # Remove user_id from session
            return redirect(url_for('login'))  # Redirect to login page after logout

    # Check if the user is logged in
    if 'user_id' in session:
        user_id = session['user_id']

        # Fetch user information from the database
        cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (user_id,))
        first_name = cursor.fetchone().first_name  # Assuming 'first_name' is the correct column name

        # Fetch transit options from the database
        cursor.execute("SELECT transit_name FROM transit")
        transit_options = [row.transit_name for row in cursor.fetchall()]

        return render_template('welcome.html', first_name=first_name, transit_options=transit_options)
    else:
        return redirect(url_for('login'))  # Redirect to login if not logged in






# TRANSIT PAGES
@app.route('/<transit_name>', methods=['GET', 'POST'])
def transit(transit_name):
    # Handle transit logic here
    return render_template(f'{transit_name}.html')





#BUYING A NEW CARD FOR TRANSIT 1


# connection string for transit_1 database
conn_str1 = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=LAPTOP-93PFC6D0\SQLEXPRESS;DATABASE=transit_1;UID=admin;PWD=admin'
conn1 = pyodbc.connect(conn_str1)
cursor1 = conn1.cursor()


# Function to get the last date of the current month
def last_day_of_month(any_day):
    next_month = any_day.replace(day=28) + timedelta(days=4)
    return (next_month - timedelta(days=next_month.day)).date()



# Route for buying a new card  for transit_1
@app.route('/buy_card', methods=['GET', 'POST'])
def buy_card():
    if request.method == 'POST':
        balance = float(request.form['balance'])
        monthly_pass = 'monthly_pass' in request.form
        expiry = last_day_of_month(datetime.now())

        # Use parameterized queries to prevent SQL injection
        cursor1.execute('''
            INSERT INTO transit_1 (balance, monthly_pass, expiry)
            VALUES (?, ?, ?)
        ''', (balance, monthly_pass, expiry))

        conn1.commit()
        return redirect(url_for('buy_card_success'))

    return render_template('buy_card.html')

# Route for showing the success page after buying a new card for transit_1

@app.route('/buy_card_success')
def buy_card_success():
    try:
        # Retrieve the latest card details from the database
        cursor1.execute('''
            SELECT  * FROM transit_1 ORDER BY serial_no DESC
        ''')

        card_details = cursor1.fetchone()

        # Check if card details are available
        if card_details:
            serial_no = card_details.serial_no
            balance = card_details.balance
            monthly_pass = card_details.monthly_pass
            expiry = card_details.expiry

            return render_template('card_details.html', serial_no=serial_no, balance=balance,
                                   monthly_pass=monthly_pass, expiry=expiry)
        else:
            return "Error retrieving card details."
    finally:
        cursor1.close()
        conn1.close()






#BUYING A NEW CARD FOR TRANSIT 2


# connection string for transit_2 database

conn_str2 = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=LAPTOP-93PFC6D0\SQLEXPRESS;DATABASE=transit_2;UID=admin;PWD=admin'
conn2 = pyodbc.connect(conn_str2)
cursor2 = conn2.cursor()


# # Function to get the last date of the current month
# def last_day_of_month_2(any_day):
#     next_month = any_day.replace(day=28) + timedelta(days=4)
#     return (next_month - timedelta(days=next_month.day)).date()



# Route for buying a new card for transit_2
@app.route('/buy_card_2', methods=['GET', 'POST'])
def buy_card_2():
    if request.method == 'POST':
        balance = float(request.form['balance'])
        monthly_pass = 'monthly_pass' in request.form
        expiry = last_day_of_month(datetime.now())

        # Use parameterized queries to prevent SQL injection
        cursor2.execute('''
            INSERT INTO transit_2 (balance, monthly_pass, expiry)
            VALUES (?, ?, ?)
        ''', (balance, monthly_pass, expiry))

        conn2.commit()
        return redirect(url_for('buy_card_success_2'))

    return render_template('buy_card_2.html')


# Route for showing the success page after buying a new card for transit_2
@app.route('/buy_card_success_2')
def buy_card_success_2():
    # Retrieve the latest card details from the transit_2 database
    cursor2.execute('''
    SELECT  * FROM transit_2 ORDER BY serial_no DESC
''')

    card_details_2 = cursor2.fetchone()

    # Check if card details are available
    if card_details_2:
        serial_no = card_details_2.serial_no
        balance = card_details_2.balance
        monthly_pass = card_details_2.monthly_pass
        expiry = card_details_2.expiry

        return render_template('card_details_2.html', serial_no=serial_no, balance=balance,
                               monthly_pass=monthly_pass, expiry=expiry)
    else:
        return "Error retrieving card details."





# LOGOUT
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    # Clear the user_id from the session
    session.pop('user_id', None)
    return redirect(url_for('login'))  # Redirect to the login page after logout




if __name__ == '__main__':
    app.run(debug=True)