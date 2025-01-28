from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
import os
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Конфигурация базы данных
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(80), nullable=True)
    surname = db.Column(db.String(80), nullable=True)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)


class Student(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    surname = db.Column(db.String(80), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    group = db.relationship('Group', backref='students')
    grades = db.Column(db.String(2000), default="{}")


# Создание базы данных
with app.app_context():
    db.create_all()


# Декоратор для защиты маршрутов
def login_required(role=None):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session['user']['role'] != role:
                return "Доступ запрещен", 403
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


@app.route('/')
def index():
    if 'user' in session and session['user']['role'] == 'teacher':
        return redirect(url_for('teacher_index'))
    elif 'user' in session and session['user']['role'] == 'student':
        return redirect(url_for('student_grades'))
    elif 'user' in session and session['user']['role'] == 'admin':
         return redirect(url_for('admin_index'))
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user'] = {'username': username, 'role': user.role}
            if user.role == 'teacher':
                return redirect(url_for('teacher_index'))
            elif user.role == 'student':
                return redirect(url_for('student_grades'))
            elif user.role == 'admin':
                return redirect(url_for('admin_index'))
        return render_template('login.html', error="Неверное имя пользователя или пароль")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        name = request.form.get('name')
        surname = request.form.get('surname')
        if role == 'student':
             if not username or not password or not name or not surname:
                return render_template('register.html', error="Заполните все поля")
             user = User(username=username, password=password, role=role, name=name, surname=surname)
             db.session.add(user)
             db.session.commit()
             return redirect(url_for('login'))
        else:
            return render_template('register.html', error="Только студенты могут регистрироваться")
    return render_template('register.html')

@app.route('/add_teacher', methods=['GET', 'POST'])
@login_required(role='admin')
def add_teacher():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
           return render_template('add_teacher.html', error="Заполните все поля", theme = session.get('theme', 'light'), username = session.get('user')['username'])
        user = User(username=username, password=password, role='teacher')
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('admin_index'))
    return render_template('add_teacher.html', theme = session.get('theme', 'light'), username = session.get('user')['username'])

@app.route('/admin')
@login_required(role='admin')
def admin_index():
    teachers = User.query.filter_by(role='teacher').all()
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('admin_index.html', theme = session.get('theme', 'light'), username=username, teachers=teachers)

@app.route('/delete_teacher/<int:teacher_id>', methods=['GET'])
@login_required(role='admin')
def delete_teacher(teacher_id):
    teacher = User.query.get(teacher_id)
    if teacher:
        db.session.delete(teacher)
        db.session.commit()
    return redirect(url_for('admin_index'))


@app.route('/change_password', methods=['GET', 'POST'])
@login_required()
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        user = User.query.filter_by(username=session['user']['username']).first()
        if user and user.password == current_password:
            user.password = new_password
            db.session.commit()
            return redirect(url_for('index'))
        else:
            return render_template('change_password.html', error="Неверный текущий пароль")
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('change_password.html',  theme = session.get('theme', 'light'), username=username)


@app.route('/toggle_theme')
def toggle_theme():
    session['theme'] = 'dark' if session.get('theme') == 'light' else 'light'
    return redirect(request.referrer or url_for('index'))


@app.route('/teacher')
@login_required(role='teacher')
def teacher_index():
    groups = Group.query.all()
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('teacher_index.html', groups=groups, theme = session.get('theme', 'light'), username=username)


@app.route('/add_group', methods=['GET', 'POST'])
@login_required(role='teacher')
def add_group():
    if request.method == 'POST':
        name = request.form.get('name')
        group = Group(name=name)
        db.session.add(group)
        db.session.commit()
        return redirect(url_for('teacher_index'))
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('add_group.html', theme = session.get('theme', 'light'), username=username)

@app.route('/delete_group/<int:group_id>', methods=['GET'])
@login_required(role='teacher')
def delete_group(group_id):
    group = Group.query.get(group_id)
    if group:
        db.session.delete(group)
        db.session.commit()
    return redirect(url_for('teacher_index'))


@app.route('/add_student/<int:group_id>', methods=['GET', 'POST'])
@login_required(role='teacher')
def add_student(group_id):
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        surname = request.form.get('surname')
        student = Student(id=student_id, name=name, surname=surname, group_id=group_id)
        db.session.add(student)
        db.session.commit()
        return redirect(url_for('view_group', group_id=group_id))
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('add_student.html', groups=Group.query.all(), group_id=group_id, theme = session.get('theme', 'light'), username=username)

@app.route('/add_grade/<string:student_id>', methods=['GET', 'POST'])
@login_required(role='teacher')
def add_grade(student_id):
    student = Student.query.get(student_id)
    if not student:
        return "Студент не найден", 404
    error = None
    if request.method == 'POST':
        subject = request.form.get('subject')
        grade = request.form.get('grade')
        if not subject or not grade:
            error = "Пожалуйста, введите предмет и оценку."
        elif not grade.isdigit() or int(grade) < 0 or int(grade) > 10:
            error = "Оценка должна быть числом от 0 до 10"
        else:
            grades_data = json.loads(student.grades) if student.grades else {}
            grades_data[subject] = grade
            student.grades = json.dumps(grades_data)
            db.session.commit()
            return redirect(url_for('view_grades', student_id=student_id))
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('add_grade.html', student=student, student_id=student_id, error=error, theme = session.get('theme', 'light'), username=username)


@app.route('/view_grades/<string:student_id>', methods=['GET', 'POST'])
@login_required()
def view_grades(student_id):
    student = Student.query.get(student_id)
    if not student:
        return "Студент не найден", 404
    group = Group.query.get(student.group_id)
    grades = json.loads(student.grades) if student.grades else {}
    error = None
    if request.method == 'POST' and session['user']['role'] == 'teacher':
        for subject, grade in request.form.items():
             if subject != 'grade' and subject !='subject':
                if grade.isdigit():
                   if int(grade) >= 0 and int(grade) <= 100:
                      grades[subject]=grade
                   else:
                     error = "Оценка должна быть числом от 0 до 100"
                     return render_template('view_grades.html', student=student, student_id=student_id, group=group, grades=grades, theme = session.get('theme', 'light'), username = session.get('user')['username'], error=error)

                elif grade == "":
                     grades[subject] = grade
                else:
                  error = "Оценка должна быть числом"
                  return render_template('view_grades.html', student=student, student_id=student_id, group=group, grades=grades, theme = session.get('theme', 'light'), username = session.get('user')['username'], error=error)

        student.grades = json.dumps(grades)
        db.session.commit()
        return redirect(url_for('view_grades', student_id=student_id))
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('view_grades.html', student=student, student_id=student_id, group=group, grades=grades, theme = session.get('theme', 'light'), username=username, error=error)


@app.route('/group/<int:group_id>')
@login_required(role='teacher')
def view_group(group_id):
    group = Group.query.get(group_id)
    if not group:
        return "Группа не найдена", 404
    group_students = Student.query.filter_by(group_id=group_id).all()
    username = session.get('user')['username'] if session.get('user') else None
    return render_template('view_group.html', group=group, students=group_students, group_id=group_id, theme = session.get('theme', 'light'), username=username)

@app.route('/delete_student/<string:student_id>/<int:group_id>', methods=['GET'])
@login_required(role='teacher')
def delete_student(student_id, group_id):
    student = Student.query.get(student_id)
    if student:
        db.session.delete(student)
        db.session.commit()
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/grades')
@login_required(role='student')
def student_grades():
    if 'user' in session:
        student = User.query.filter_by(username=session['user']['username']).first()
        if not student:
            return "Студент не найден", 404
        return redirect(url_for('view_grades', student_id=student.username))
    else:
        return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)