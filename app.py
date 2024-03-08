from flask import Flask, render_template, redirect, request, flash, send_file, session, jsonify, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired
from flask_login import UserMixin, LoginManager,current_user
from bson.objectid import ObjectId
from urllib.parse import quote_plus
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import os
from flask_login import login_user,login_required, current_user
from pymongo import MongoClient
from werkzeug.security import check_password_hash,generate_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key'

client = MongoClient(
    host="mongodb+srv://nagi:nagi@cluster0.ohv5gsc.mongodb.net/nagidb",
    authMechanism="SCRAM-SHA-1"
)

# Access the desired database
db = client["TechSpeak_Web"]

# Create the collections
courses_collection = db["courses"]
exams_collection = db["exams"]
grades_collection = db["grades"]
notes_collection = db["notes"]
# questions_collection = db["questions"] 
papers_collection = db["papers"]
# Configuration for file upload
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, _id, username, email, password, payment_status=False):
        self._id = _id
        self.username = username
        self.email = email
        self.password = password
        self.payment_status = payment_status


@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        user = User(_id=user_data['_id'], username=user_data['username'], email=user_data['email'], password=user_data['password'])
    return user

## Define MongoDB models
class School:
    def __init__(self, name, description):
        self.name = name
        self.description = description

class Department:
    def __init__(self, name, school_id, description):
        self.name = name
        self.school_id = school_id
        self.description = description

class Course:
    def __init__(self, name, department_id, description):
        self.name = name
        self.department_id = department_id
        self.description = description

# Define WTForms for your forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

class AdminLoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')



@app.route('/')
def index():
    user_id = session.get('user_id')
    user = None
    if user_id:
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            # Check if 'email' field is present in user_data
            if 'email' in user_data:
                user = User(**user_data)
            else:
                # If 'email' is missing, handle the situation accordingly (e.g., redirect to login)
                return redirect(url_for('login'))

    num_questions_answered = 10  # Replace with your logic to calculate the number of questions answered
    courses = list(db["courses"].find())  # Fetch all courses from the "courses" collection
    exams = list(db["exams"].find())  # Fetch all exams from the "exams" collection
    grades = list(db["grades"].find())  # Fetch all grades from the "grades" collection
    notes = list(db["notes"].find())  # Fetch all notes from the "notes" collection

    return render_template('studentdashboard.html', user=user, num_questions_answered=num_questions_answered,
                           courses=courses, exams=exams, grades=grades, notes=notes)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Query user data from MongoDB
        user_data = db.users.find_one({'email': email, 'password': password, 'is_admin': True})
        
        if user_data:
            # Create a User object using the retrieved data
            user = User(**user_data)
            login_user(user)  # Log in the user
            return redirect('/admin/home')
        else:
            flash('Invalid credentials', 'error')

    return render_template('admins/admin_login.html', form=form)

@app.route('/admin/home')
@login_required
def admin_home():
    # Check if the current user is an admin
    if current_user.is_admin:
        return render_template('admins/home.html')  # Render the admin homepage
    else:
        flash('You do not have permission to access this page.', 'error')
        return redirect('/')  # Redirect to the regular homepage
    
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_user_id' in session:
        return redirect('/admin')
    else:
        return redirect('/admin/login')

@app.route('/admin/initialize')
def initialize_admin_user():
    admin_user_count = User.objects().count()
    if admin_user_count == 0:
        initial_admin_user = {
            'email': 'admin@example.com',
            'password': 'admin_password',
        }
        admin_user = User(**initial_admin_user)
        admin_user.save()
        return 'Admin user initialized successfully'
    else:
        return 'Admin user already exists'

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if username or email already exists
        existing_user = db.users.find_one({'$or': [{'username': username}, {'email': email}]})
        if existing_user:
            error = 'Username or email already exists'
            return render_template('signup.html', error=error)
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        # Create a new user document
        user = {
            'username': username,
            'email': email,
            'password': hashed_password
        }
        
        # Insert the new user into the database
        db.users.insert_one(user)
        
        # Redirect to the login page with a success message
        return redirect(url_for('login'))
    
    # If GET request, render the signup form
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate email and password
        if email and password:
            # Find user by email
            user = db.users.find_one({'email': email})
            if user and check_password_hash(user['password'], password):
                # Store user ID in session
                session['user_id'] = str(user['_id'])
                return redirect(url_for('index'))
            else:
                error_message = "Invalid email or password. Please try again."
                return render_template('Login.html', error=error_message)
        else:
            error_message = "Email and password are required."
            return render_template('Login.html', error=error_message)
    
    # If it's a GET request, render the login form
    return render_template('Login.html')

   
@app.route('/payment', methods=['GET', 'POST'])
def handle_payment():
    if request.method == 'GET':
        selected_plan = request.args.get('plan')

        if selected_plan:
            amount = get_payment_amount(selected_plan)
            if amount is not None:
                total_payment = amount + 250
                return render_template('payment_confirmation.html', plan=selected_plan, amount=amount,
                                       total_payment=total_payment)
            else:
                return jsonify({'error': 'Invalid plan selected'})

    if request.method == 'POST':
        user_id = session.get('new_user_id')
        if user_id:
            user = User.objects(id=ObjectId(user_id)).first()
            if user and not user.payment_status:
                selected_plan = request.form.get('plan')
                amount = get_payment_amount(selected_plan)

                if amount is not None:
                    total_payment = amount + 250
                    payment_confirmed = True  # Simulate payment confirmation
                    if payment_confirmed:
                        user.update(set__payment_status=True)
                        session.pop('new_user_id')
                        return jsonify({'success': 'Payment confirmed', 'amount': amount,
                                        'total_payment': total_payment})
                    else:
                        return jsonify({'error': 'Payment failed'})

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


@app.route('/courses/upload', methods=['GET', 'POST'])
def upload_course():
    if request.method == 'POST':
        # Get the course details from the form
        course_name = request.form['course_name']
        course_description = request.form['course_description']

        # Create a new course document
        course = {
            'name': course_name,
            'description': course_description
        }

        # Insert the course into the "courses" collection
        db["courses"].insert_one(course)

        # Redirect to the main dashboard page with a success message
        session['course_added'] = True
        return redirect(url_for('index'))

    return render_template('upload_course.html')

@app.route('/papers/<filename>', methods=['GET'])
def get_paper(filename):
    # Construct the path to the uploaded paper
    paper_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Check if the paper exists
    if os.path.exists(paper_path):
        # Serve the paper file
        return send_file(paper_path, as_attachment=True)
    else:
        # Return a 404 error if the paper does not exist
        return render_template('404_temp.html')

@app.route('/upload-paper', methods=['GET', 'POST'])
def upload_paper():
    if request.method == 'POST':
        course_name = request.form.get('course_name')
        paper_file = request.files.get('paper')

        # Check if the file is valid and allowed
        if paper_file and allowed_file(paper_file.filename):
            # Secure the filename and save the file to the upload folder
            filename = secure_filename(paper_file.filename)
            paper_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Generate the paper link
            paper_link = url_for('get_paper', filename=filename, _external=True)

            # Find the course ID based on the selected course name
            course = courses_collection.find_one({'name': course_name})
            if course:
                course_id = course['_id']

                # Store the link to the paper in the papers collection
                paper = {
                    'course_id': course_id,
                    'paper_link': paper_link
                }
                papers_collection.insert_one(paper)

                session['paper_added'] = True
                return redirect(url_for('index'))
            else:
                error_message = "Selected course not found."
                return render_template('upload-paper.html', error=error_message)

    # Fetch the list of courses to display in the form
    courses = courses_collection.find()
    return render_template('upload-paper.html', courses=courses)

# Function to get questions for a given course_id
def get_questions_for_course(course_id):
    # Assuming you have a MongoDB collection named 'questions'
    questions = db.questions.find({'course_id': course_id})
    return list(questions)

# Function to get course details for a given course_id
def get_course_details(course_id):
    # Assuming you have a MongoDB collection named 'courses'
    course = db.courses.find_one({'_id': ObjectId(course_id)})
    return course

@app.route('/courses')
def courses():
    courses = db.courses.find() 
    courses = list(db.courses.find())  # Fetch all courses from the "courses" collection
    for course in courses:
        # Count the number of papers for each course
        course['num_papers'] = db.questions.count_documents({'course_id': course['_id']})
 # Fetch all courses from the database
    return render_template('Courses.html', courses=courses)

@app.route('/questions/<course_id>')
def display_questions(course_id):
    # Fetch the course details based on the course_id
    course = db.courses.find_one({'_id': ObjectId(course_id)})
    if course:
        # Fetch all questions for the given course
        questions = db.questions.find({'course_id': course_id})
        return render_template('viewpaper.html', course=course, questions=questions)
    else:
        # Handle the case where the course is not found
        flash('Course not found.', 'error')
        return redirect(url_for('profile')) 
    
@app.route('/papers/<course_id>')
def papers(course_id):
    course = get_course_details(course_id)  # Fetch the selected course
    papers = get_papers_for_course(course_id)  # Fetch papers for the selected course
    return render_template('papers.html', course=course, papers=papers)

def get_papers_for_course(course_id):
    papers = papers_collection.find({'course_id': course_id})  # Assuming 'papers_collection' is your collection
    return list(papers)

# @app.route('/course/<course_id>/questions')
# def course_questions(course_id):
#     course = courses_collection.find_one({'_id': ObjectId(course_id)})
#     if course:
#         # Fetch questions for the given course from the database
#         questions = questions_collection.find({'course_id': course_id})
#         return render_template('course_questions.html', course=course, questions=questions)
#     else:
#         # Handle case where course is not found
#         return "Course not found", 404
    

@app.route('/404')
def notfound():
    return render_template('404_temp.html')

@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    user = None
    if user_id:
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            # Check if 'email' field is present in user_data
            if 'email' in user_data:
                user = User(**user_data)
            else:
                # If 'email' is missing, handle the situation accordingly (e.g., redirect to login)
                return redirect(url_for('login'))

    num_questions_answered = 10  # Replace with your logic to calculate the number of questions answered
    courses = list(db["courses"].find())  # Fetch all courses from the "courses" collection
    exams = list(db["exams"].find())  # Fetch all exams from the "exams" collection
    grades = list(db["grades"].find())  # Fetch all grades from the "grades" collection
    notes = list(db["notes"].find())  # Fetch all notes from the "notes" collection

    return render_template('Profile.html', user=user, num_questions_answered=num_questions_answered,
                           courses=courses, exams=exams, grades=grades, notes=notes)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8100, debug=True)
