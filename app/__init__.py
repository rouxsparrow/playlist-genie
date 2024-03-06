from flask import Flask
from flask_session import Session
from .views import main
import os

def create_app():
    app = Flask(__name__)
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)
    app.register_blueprint(main)
    return app
