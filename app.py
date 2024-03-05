from flask import Flask, flash, jsonify, render_template, request, redirect, session, url_for
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import urllib.parse
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.pymongo import ModelView
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from wtforms import SelectField
from flask_login import current_user

app = Flask(__name__)
app.secret_key = 'your-secret-key'
csrf = CSRFProtect(app)

# MongoDB Configuration
username = "joeltabe3"
password = "j0@lmessi"
cluster_name = "cluster0"
database_name = "quizzy"

# Escape username and password
escaped_username = urllib.parse.quote_plus(username)
escaped_password = urllib.parse.quote_plus(password)

# Create a new client and connect to the server
client = MongoClient(f"mongodb+srv://{escaped_username}:{escaped_password}@{cluster_name}.dw2mdqb.mongodb.net/{database_name}?retryWrites=true&w=majority")
db = client[database_name]

# Define the login form
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Define the signup form
class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

class AdminLoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SchoolForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Create')

class DepartmentForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    school_id = SelectField('School', coerce=str, validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Create')

class CourseForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    department_id = SelectField('Department', coerce=str, validators=[DataRequired()])
    description = StringField('Description', validators=[DataRequired()])
    submit = SubmitField('Create')

# Define the admin views
class UserAdminView(ModelView):
    column_list = ('username', 'email', 'password')
    form = SignupForm

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

class SchoolAdminView(ModelView):
    column_list = ('name', 'description')
    form_columns = ('name', 'description')

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def scaffold_form(self):
        class _SchoolForm(FlaskForm):
            name = StringField('Name', validators=[DataRequired()])
            description = StringField('Description', validators=[DataRequired()])
            submit = SubmitField('Create')

        return _SchoolForm

class DepartmentAdminView(ModelView):
    column_list = ('name', 'school_id', 'description')
    form_columns = ('name', 'school_id', 'description')

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def scaffold_form(self):
        class _DepartmentForm(FlaskForm):
            name = StringField('Name', validators=[DataRequired()])
            school_id = SelectField('School', coerce=str, validators=[DataRequired()])
            description = StringField('Description', validators=[DataRequired()])
            submit = SubmitField('Create')

        return _DepartmentForm

class CourseModel(db.courses):
    column_list = ('name', 'department_id', 'description')
    form_columns = ('name', 'department_id', 'description')

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def scaffold_form(self):
        class _CourseForm(FlaskForm):
            name = StringField('Name', validators=[DataRequired()])
            department_id = SelectField('Department', coerce=str, validators=[DataRequired()])
            description = StringField('Description', validators=[DataRequired()])
            submit = SubmitField('Create')

        return _CourseForm

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return True

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('dashboard'))

admin = Admin(app, index_view=MyAdminIndexView())

# Add views for each MongoDB collection
admin.add_view(ModelView(SchoolModel))
admin.add_view(ModelView(DepartmentModel))
admin.add_view(ModelView(CourseModel))
admin.add_view(ModelView(UserModel))

admin_users_collection = db["admin_users"]
# Create collections for forms if they don't exist
def create_collections():
    if "users" not in db.list_collection_names():
        db.create_collection("users")

    if "departments" not in db.list_collection_names():
        db.create_collection("departments")

    if "courses" not in db.list_collection_names():
        db.create_collection("courses")

    if "schools" not in db.list_collection_names():
        db.create_collection("schools")

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if user:
            return render_template('quizzy.html')
    return redirect('/login')

# Routes...

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if the admin user exists in the database
        admin_user = admin_users_collection.find_one({'email': email})
        if admin_user:
            # Verify the password
            if admin_user.get('password') == password:
                # Perform admin login
                # You can use Flask-Login for admin authentication if needed
                session['admin_user_id'] = str(admin_user['_id'])
                return redirect('/admin/dashboard')  # Redirect to the admin dashboard
            else:
                flash('Invalid email or password', 'error')
        else:
            flash('Invalid email or password', 'error')

    return render_template('admins/admin_login.html', form=form)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_user_id' in session:
        # Check if the admin is logged in
        # Render the Flask-Admin interface
        return redirect('/admin')
    else:
        return redirect('/admin/login')

# Define a route to insert the initial admin user into the database
@app.route('/admin/initialize')
def initialize_admin_user():
    # Check if there are no existing admin users
    if admin_users_collection.count_documents({}) == 0:
        # Insert the initial admin user (e.g., John Doe)
        initial_admin_user = {
            'email': 'admin@example.com',
            'password': 'admin_password',
            # Add other admin user fields as needed
        }
        admin_users_collection.insert_one(initial_admin_user)
        return 'Admin user initialized successfully'
    else:
        return 'Admin user already exists'

# Other route
    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        # Check if username or email already exists
        if db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
            return 'Username or email already taken'

        # Create new user with initial payment status set to False
        user = {'username': username, 'email': email, 'password': password, 'payment_status': False}
        db.users.insert_one(user)
        
        # Redirect to the payment page
        session['new_user_id'] = str(user['_id'])  # Store the newly created user's ID in the session
        return redirect('/payment-page')
    
    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Check if the user with the provided email exists in the database
        user = db.users.find_one({'email': email})
        if user:
            # Verify the password
            if user.get('password') == password:
                session['user_id'] = str(user['_id'])
                return redirect('/')  # Redirect to the user dashboard
            else:
                return 'Invalid credentials'  # Incorrect password
        else:
            return 'Invalid credentials'  # User not found

    return render_template('Login.html', form=form)

@app.route('/payment', methods=['GET', 'POST'])
def handle_payment():
    if request.method == 'GET':
        selected_plan = request.args.get('plan')

        if selected_plan:
            amount = get_payment_amount(selected_plan)
            if amount is not None:
                total_payment = amount + 250
                # Render the payment confirmation template with the selected plan, amount, and total payment
                return render_template('payment_confirmation.html', plan=selected_plan, amount=amount, total_payment=total_payment)

            # Handle the case when the plan is not valid
            return jsonify({'error': 'Invalid plan selected'})

    if request.method == 'POST':
        user_id = session.get('new_user_id')

        # Check if a new user ID is stored in the session
        if user_id:
            # Retrieve the user document from the database
            user = db.users.find_one({'_id': ObjectId(user_id)})

            # Check if the user exists and the payment status is False
            if user and not user['payment_status']:
                selected_plan = request.form.get('plan')
                amount = get_payment_amount(selected_plan)

                if amount is not None:
                    total_payment = amount + 250
                    # Simulate payment confirmation
                    payment_confirmed = True

                    if payment_confirmed:
                        # Update the payment status in the database
                        db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'payment_status': True}})

                        # Remove the user ID from the session
                        session.pop('new_user_id')

                        return jsonify({'success': 'Payment confirmed', 'amount': amount, 'total_payment': total_payment})
                    else:
                        return jsonify({'error': 'Payment failed'})

                # Handle the case when the plan is not valid
                return jsonify({'error': 'Invalid plan selected'})

        return jsonify({'error': 'Invalid request'})

def get_payment_amount(plan):
    if plan == 'basic':
        return 10000
    elif plan == 'premium':
        return 20000
    elif plan == 'enterprise':
        return 30000

    return None
    
@app.route('/payment-page')
def payment_page():
    return render_template('payment.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
 
    # Create collections for forms if they don't exist
    create_collections()  # Call the function to create collections if they don't exist
    app.run(debug=True)