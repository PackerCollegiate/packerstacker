from flask import render_template, flash, redirect, url_for
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm, EmptyForm, QuestionForm, ReplyForm
from flask_login import current_user, login_user
from app.models import User, Question, Reply, Tag
from flask_login import logout_user
from flask_login import login_required
from flask import request
from werkzeug.urls import url_parse
from datetime import datetime
from sqlalchemy import or_

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = QuestionForm()
    if form.validate_on_submit():
        question = Question(body=form.question.data, author=current_user)
        db.session.add(question)

        tag_names = form.tags.data
        for name in tag_names:
            tag = Tag.query.filter_by(name=name.strip()).first()
            if not tag:
                tag = Tag(name=name.strip())
                db.session.add(tag)
            question.tags.append(tag)

        db.session.commit()
        flash('Your question is now live!')
        return redirect(url_for('index'))
    page = request.args.get('page', 1, type=int)
    questions = current_user.followed_questions().paginate(
        page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('index', page=questions.next_num) \
        if questions.has_next else None
    prev_url = url_for('index', page=questions.prev_num) \
        if questions.has_prev else None
    return render_template('index.html', title='Home', form=form,
                           questions=questions.items, next_url=next_url,
                           prev_url=prev_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, type = form.type.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    questions = user.questions.order_by(Question.timestamp.desc()).paginate(
        page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('user', username=user.username, page=questions.next_num) \
        if questions.has_next else None
    prev_url = url_for('user', username=user.username, page=questions.prev_num) \
        if questions.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, questions=questions.items,
                           next_url=next_url, prev_url=prev_url, form=form)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',form=form)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash('You are following {}!'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash('User {} not found.'.format(username))
            return redirect(url_for('index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash('You are not following {}.'.format(username))
        return redirect(url_for('user', username=username))
    else:
        return redirect(url_for('index'))

@app.route('/explore')
def explore():
    page = request.args.get('page', 1, type=int)
    tags = Tag.query.order_by(Tag.name)
    questions = Question.query.order_by(Question.timestamp.desc()).paginate(page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('explore', page=questions.next_num) \
        if questions.has_next else None
    prev_url = url_for('explore', page=questions.prev_num) \
        if questions.has_prev else None
    return render_template("explore.html", title='Explore', tags=tags, questions=questions.items,next_url=next_url, prev_url=prev_url)

@app.route('/q/<id>', methods=['GET', 'POST'])
def question_page(id):
    question = Question.query.filter_by(id=id).first_or_404()
    page = request.args.get('page', 1, type=int)
    form = ReplyForm()
    if form.validate_on_submit():
        reply = Reply(body=form.reply.data, author=current_user, op=question)
        db.session.add(reply)
        db.session.commit()
        flash('Thanks for answering!')
        return redirect(url_for('question_page', id=id))
    page = request.args.get('page', 1, type=int)
    replies = question.q_replies().paginate(
        page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('q/<id>', page=replies.next_num) \
        if replies.has_next else None
    prev_url = url_for('q/<id>', page=replies.prev_num) \
        if replies.has_prev else None
    return render_template("question_page.html", title='Question', form=form, question=question,
        replies=replies.items, next_url=next_url, prev_url=prev_url)

@app.route('/tag/<id>')
def tag_page(id):
    tag = Tag.query.filter_by(id=id).first_or_404()
    page = request.args.get('page', 1, type=int)
    questions = tag.tag_questions().paginate(
        page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('tag/<id>', tag=tag.id, page=questions.next_num) \
        if questions.has_next else None
    prev_url = url_for('tag/<id>', tag=tag.id, page=questions.prev_num) \
        if questions.has_prev else None
    form = EmptyForm()
    return render_template('tag_page.html', tag=tag.name, questions=questions.items,
                           next_url=next_url, prev_url=prev_url, form=form)

@app.route('/search', methods=['POST'])
def search():
    search_terms = request.form['search'].split()
    first_q = Tag.query.filter_by(name=search_terms[0]).first_or_404()
    questions = first_q.tag_questions()
    if len(search_terms) >1:
        for i in range(1,len(search_terms)):
            new_q=Tag.query.filter_by(name=search_terms[i]).first_or_404()
            new_questions = new_q.tag_questions()
            questions = questions.union(new_questions).all()
    page = request.args.get('page', 1, type=int)
    questions = questions.paginate(
        page=page, per_page=app.config['QUESTIONS_PER_PAGE'], error_out=False)
    next_url = url_for('search', name=name, page=questions.next_num) \
        if questions.has_next else None
    prev_url = url_for('search', name=name, page=questions.prev_num) \
        if questions.has_prev else None
    form = EmptyForm()
    return render_template('search_results.html', questions=questions.items,
                           next_url=next_url, prev_url=prev_url, form=form)

@app.route('/boy')
def boy():
    print('hello world')
    return render_template('boy.html')
