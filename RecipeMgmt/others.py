from functools import wraps
from enum import Enum
from flask import abort, redirect, session, url_for
from bson import json_util
import os
import json

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = APP_ROOT + "/static"


def parse_json(data):
    return json.loads(json_util.dumps(data))


# Session
def start_session(user):
    session['logged_in'] = True
    del user['password']
    # user['_id'] = str(user['_id'])
    session['user'] = parse_json(user)


# Decorators
def login_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return fn(*args, **kwargs)
        else:
            return redirect("/")

    return wrap


def admin_only(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if 'is_admin' in session:
            return fn(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page")

    return wrap


def user_only(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if 'is_user' in session:
            return fn(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page")

    return wrap


class RecipeStatus(Enum):
    Pending = 0
    Rejected = 1
    Approved = 2
