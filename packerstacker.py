from app import app, db
from app.models import User, Question, Reply, Tag

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Question': Question, 'Reply': Reply, 'Tag':Tag}
