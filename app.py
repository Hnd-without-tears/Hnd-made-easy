from flask import Flask, render_template, redirect, request, flash, session, jsonify
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

app = Flask(__name__)
app.secret_key = 'your-secret-key'

escaped_username = quote_plus('joeltabe3')
escaped_password = quote_plus('j0@lmessi')

client = MongoClient(f"mongodb+srv://{escaped_username}:{escaped_password}@cluster0.dw2mdqb.mongodb.net/quizapp")
db = client.quizapp

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

# Define WTForms for your forms
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

class PaperUploadForm(FlaskForm):
    course_id = SelectField('Course', coerce=str, validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    file_url = StringField('File URL', validators=[DataRequired()])
    submit = SubmitField('Upload Paper')

@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id:
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            user = User(**user_data)
            return render_template('quizzy.html', user=user)
    return render_template('quizzy.html', user=user)


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
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        # Query MongoDB to check if the email or username already exists
        existing_user = db.users.find_one({'$or': [{'email': email}, {'username': username}]})
        if existing_user:
            return 'Username or email already taken'

        # Create a new user document and insert it into the database
        new_user_data = {
            'username': username,
            'email': email,
            'password': password,
            'payment_status': False
        }
        db.users.insert_one(new_user_data)
        session['new_user_id'] = str(new_user_data['_id'])
        return redirect('/payment-page')

    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Query user data from MongoDB
        user_data = db.users.find_one({'email': email, 'password': password})
        
        if user_data:
            session['user_id'] = str(user_data['_id'])
            flash('Login successful!', 'success')
            return redirect('/')
        else:
            flash('Invalid email or password', 'error')

    return render_template('Login.html', form=form)


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

@app.route('/view-papers')
def view_papers():
    # Fetch paper data from the database
    papers = db.papers.find()

    # Organize papers by course for easier rendering in the template
    papers_by_course = {}
    for paper in papers:
        course_id = paper.get('course_id')
        course = db.courses.find_one({'_id': course_id})
        if course:
            department_id = course.get('department')
            department = db.departments.find_one({'_id': department_id})
            if department:
                school_id = department.get('school')
                school = db.schools.find_one({'_id': school_id})
                if school:
                    school_name = school.get('name')
                    department_name = department.get('name')
                    course_name = course.get('name')
                    full_course_name = f"{school_name} - {department_name} - {course_name}"
                    if full_course_name not in papers_by_course:
                        papers_by_course[full_course_name] = []
                    papers_by_course[full_course_name].append(paper)

    return render_template('viewpaper.html', papers_by_course=papers_by_course)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload-paper', methods=['GET', 'POST'])
def upload_paper():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Now you can save other form data to the database if needed
            # Redirect to a success page or wherever you want
            return redirect('/')
        else:
            flash('Invalid file format. Please upload a PDF file.')
            return redirect(request.url)
    else:
        # Handle GET request for showing the form (if needed)
        return render_template('upload-paper.html')

    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Now you can save other form data to the database if needed
        # Redirect to a success page or wherever you want
        return redirect('/')
    else:
        flash('Invalid file format. Please upload a PDF file.')
        return redirect(request.url)

# Routes for courses
@app.route('/courses', methods=['GET', 'POST'])
def create_course():
    form = CourseForm()
    form.department_id.choices = [(str(department['_id']), department['name']) for department in db.departments.find()]
    if form.validate_on_submit():
        name = form.name.data
        department_id = form.department_id.data
        description = form.description.data
        course = Course(name, ObjectId(department_id), description)
        db.courses.insert_one(course.__dict__)  # Insert course into MongoDB
        flash('Course created successfully!', 'success')
        return redirect('/courses')
    return render_template('Courses.html', form=form)

@app.route('/courses/delete/<string:course_id>', methods=['POST'])
def delete_course(course_id):
    db.courses.delete_one({'_id': ObjectId(course_id)})
    flash('Course deleted successfully!', 'success')
    return redirect('/courses')

@app.route('/schools', methods=['GET', 'POST'])
def create_school():
    form = SchoolForm()
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        school = School(name, description)
        db.schools.insert_one(school.__dict__)  # Insert school into MongoDB
        flash('School created successfully!', 'success')
        return redirect('/schools')
    return render_template('schools.html', form=form)

@app.route('/schools/delete/<string:school_id>', methods=['POST'])
def delete_school(school_id):
    db.schools.delete_one({'_id': ObjectId(school_id)})
    flash('School deleted successfully!', 'success')
    return redirect('/schools')

# Routes for departments
@app.route('/departments', methods=['GET', 'POST'])
def create_department():
    form = DepartmentForm()
    form.school_id.choices = [(str(school['_id']), school['name']) for school in db.schools.find()]
    if form.validate_on_submit():
        name = form.name.data
        school_id = form.school_id.data
        description = form.description.data
        department = Department(name, ObjectId(school_id), description)
        db.departments.insert_one(department.__dict__)  # Insert department into MongoDB
        flash('Department created successfully!', 'success')
        return redirect('/departments')
    return render_template('departments.html', form=form)

@app.route('/departments/delete/<string:department_id>', methods=['POST'])
def delete_department(department_id):
    db.departments.delete_one({'_id': ObjectId(department_id)})
    flash('Department deleted successfully!', 'success')
    return redirect('/departments')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8100, debug=True)
