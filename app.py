import secrets
import bcrypt
import logging
import os
from flask import Flask, redirect, request, render_template
from flask_restx import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt, verify_jwt_in_request
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:////app/data/pictochat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or secrets.token_hex(32)

db = SQLAlchemy(app)
jwt = JWTManager(app)

api = Api(app, version='1.0', title='Pictochat API', doc='/swagger', prefix='/api')

logging.basicConfig(filename=os.environ.get('AUDIT_LOG_PATH') or '/app/logs/audit.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

class ApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, user_id):
        self.user_id = user_id
        self.key = secrets.token_hex(32)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    api_keys = db.relationship('ApiKey', backref='user', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(32), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/')
def inicio():
    return redirect('/login.html')

@app.route('/login.html')
def ruta_login():
    return render_template('login.html')

@app.route('/register.html')
def ruta_registro():
    return render_template('register.html')

@app.route('/chat.html')
def ruta_chat():
    return render_template('chat.html')

def validate_content_type(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT']:
            if request.headers.get('Content-Type') != 'application/json':
                return {'message': 'Unsupported Media Type'}, 415
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') != role:
                return {'message': 'No autorizado'}, 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request(optional=True)
        if get_jwt_identity():
            return f(*args, **kwargs)

        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return {'message': 'API key required'}, 401
        
        key = ApiKey.query.filter_by(key=api_key).first()
        if not key:
            logging.warning(f"Invalid API key attempt: {api_key}")
            return {'message': 'Invalid API key'}, 401
        logging.info(f"API key {api_key} used for request {request.path}")
        return f(*args, **kwargs)
    return decorated_function

def register():
    data = request.json or {}
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password:
        return {'message': 'Usuario y contraseña son obligatorios'}, 400
    if username.lower() == 'admin':
        return {'message': 'Nombre de usuario no permitido'}, 400
    if User.query.filter_by(username=username).first():
        return {'message': 'Usuario existente'}, 400
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.session.add(User(username=username, password=hashed, role='user'))
    db.session.commit()
    logging.info(f"Registro: {username}")
    return {'message': 'Usuario registrado con éxito'}, 201

class RegisterResource(Resource):
    def post(self):
        return register()

class LoginResource(Resource):
    def post(self):
        return login()

class ApiKeyResourceWrapper(Resource):
    method_decorators = [jwt_required()]
    def post(self):
        return api_key_resource()

class ChatResource(Resource):
    method_decorators = [api_key_required]
    def get(self):
        return chat_get()
    @validate_content_type
    def post(self):
        return chat_post()

class ChatItemResource(Resource):
    method_decorators = [validate_content_type, role_required('admin'), jwt_required()]
    def put(self, message_id):
        return chat_put(message_id)
    def delete(self, message_id):
        return chat_delete(message_id)

api.add_resource(RegisterResource, '/register')
api.add_resource(LoginResource, '/login')
api.add_resource(ApiKeyResourceWrapper, '/api-key')
api.add_resource(ChatResource, '/chat')
api.add_resource(ChatItemResource, '/chat/<int:message_id>')

def login():
    try:
        data = request.json or {}
        username = data.get('username')
        logging.info(f"Attempted login for user: {username}")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.checkpw(data.get('password','').encode('utf-8'), user.password.encode('utf-8')):
            token = create_access_token(identity=user.username, additional_claims={'role': user.role})
            logging.info(f"User logged in: {username}")
            return {'access_token': token, 'username': user.username, 'role': user.role}, 200
        logging.warning(f"Invalid credentials for user: {username}")
        return {'message': 'Credenciales inválidas'}, 401
    except Exception as e:
        logging.error(f"Error in login: {e}")
        return {'message': 'Internal server error'}, 500

def api_key_resource():
    current_user_username = get_jwt_identity()
    user = User.query.filter_by(username=current_user_username).first()
    if not user:
        return {'message': 'User not found'}, 404
    existing = ApiKey.query.filter_by(user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        logging.info(f"API key revoked for user {current_user_username}")
    api_key = ApiKey(user_id=user.id)
    db.session.add(api_key)
    db.session.commit()
    logging.info(f"API key created for user {current_user_username}")
    return {'api_key': api_key.key}, 201

def chat_get():
    msgs = Message.query.order_by(Message.timestamp.asc()).all()
    return [{'id': m.id, 'content': m.content, 'author': m.author, 'date': m.timestamp.strftime("%H:%M")} for m in msgs], 200

def chat_post():
    data = request.json or {}
    content = data.get('content','').strip()
    if not content:
        return {'message': 'Content is required'}, 400
    author = get_jwt_identity()
    if not author:
        api_key = request.headers.get('X-API-KEY')
        key = ApiKey.query.filter_by(key=api_key).first()
        author = key.user.username if key and key.user else 'unknown'
    new_msg = Message(content=content, author=author)
    db.session.add(new_msg)
    db.session.commit()
    logging.info(f"Message posted by {author}: {content}")
    return {'message': 'Mensaje enviado'}, 201

def chat_put(message_id):
    try:
        data = request.json or {}
        msg = Message.query.get_or_404(message_id)
        content = data.get('content', '').strip()
        if not content:
            return {'message': 'Content is required'}, 400
        msg.content = content
        db.session.commit()
        logging.info(f"Message {message_id} edited by admin {get_jwt_identity()}")
        return {'message': 'Editado'}, 200
    except Exception as e:
        logging.error(f"Error editing message {message_id}: {e}")
        return {'message': 'Internal server error'}, 500

def chat_delete(message_id):
    try:
        msg = Message.query.get_or_404(message_id)
        db.session.delete(msg)
        db.session.commit()
        logging.info(f"Message {message_id} deleted by admin {get_jwt_identity()}")
        return {'message': 'Eliminado'}, 200
    except Exception as e:
        logging.error(f"Error deleting message {message_id}: {e}")
        return {'message': 'Internal server error'}, 404

@app.errorhandler(404)
def not_found(error):
    return {'message': 'Resource Not Found'}, 404

@app.errorhandler(405)
def method_not_allowed(error):
    return {'message': 'Method Not Allowed'}, 405

@app.errorhandler(400)
def bad_request(error):
    return {'message': 'Bad Request'}, 400

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db.session.add(User(username='admin', password=hashed, role='admin'))
            db.session.commit()
            logging.info('Default admin user created')
    app.run(host='0.0.0.0', debug=True, port=5000, ssl_context='adhoc')