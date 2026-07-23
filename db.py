"""
MongoDB layer for ScriptToStock.
Collections:
  users    : {username, password_hash, active, balance_usd, total_spent_usd, runs, created_at}
  usage    : {username, ts, title, actual_cost_usd, charged_usd, scenes, videos, images, duration_s}
  settings : single doc _id='config' → {claude_key, pexels_key, markup}
Env:
  MONGODB_URI  (required)   MONGODB_DB (default 'scripttostock')
  CLAUDE_API_KEY / PEXELS_API_KEY (fallbacks if not set in settings)
"""
import os
import time

from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash, check_password_hash

_client = None

DEFAULT_MARKUP = 5.0


def get_db():
    global _client
    if _client is None:
        uri = os.environ.get('MONGODB_URI')
        if not uri:
            raise Exception('MONGODB_URI environment variable is not set')
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        db = _client[os.environ.get('MONGODB_DB', 'scripttostock')]
        try:
            db.users.create_index([('username', ASCENDING)], unique=True)
            db.usage.create_index([('username', ASCENDING), ('ts', DESCENDING)])
        except Exception:
            pass  # index creation is best-effort (e.g. read-only user)
    return _client[os.environ.get('MONGODB_DB', 'scripttostock')]


# ── Users ────────────────────────────────────────────────────────────────────

def create_user(username, password, balance_usd=0.0):
    username = username.strip().lower()
    if not username or not password:
        raise ValueError('Username and password are required')
    db = get_db()
    if db.users.find_one({'username': username}):
        raise ValueError(f'User "{username}" already exists')
    db.users.insert_one({
        'username': username,
        'password_hash': generate_password_hash(password),
        'active': True,
        'balance_usd': round(float(balance_usd), 4),
        'total_spent_usd': 0.0,
        'runs': 0,
        'created_at': time.time(),
    })


def verify_user(username, password):
    """Return the user doc if credentials are valid, else None."""
    user = get_db().users.find_one({'username': username.strip().lower()})
    if user and check_password_hash(user.get('password_hash', ''), password):
        return user
    return None


def get_user(username):
    return get_db().users.find_one({'username': username.strip().lower()})


def list_users():
    return list(get_db().users.find({}, {'password_hash': 0}).sort('created_at', ASCENDING))


def set_user_active(username, active):
    get_db().users.update_one(
        {'username': username.strip().lower()},
        {'$set': {'active': bool(active)}}
    )


def set_user_password(username, password):
    get_db().users.update_one(
        {'username': username.strip().lower()},
        {'$set': {'password_hash': generate_password_hash(password)}}
    )


def add_credit(username, amount_usd):
    get_db().users.update_one(
        {'username': username.strip().lower()},
        {'$inc': {'balance_usd': round(float(amount_usd), 4)}}
    )


def delete_user(username):
    username = username.strip().lower()
    db = get_db()
    db.users.delete_one({'username': username})
    db.usage.delete_many({'username': username})


def charge_user(username, actual_cost_usd, charged_usd, title, metadata):
    """Deduct a run's cost from the user's balance and log it."""
    db = get_db()
    db.users.update_one(
        {'username': username},
        {'$inc': {
            'balance_usd': -round(charged_usd, 4),
            'total_spent_usd': round(charged_usd, 4),
            'runs': 1,
        }}
    )
    db.usage.insert_one({
        'username': username,
        'ts': time.time(),
        'title': title[:120],
        'actual_cost_usd': round(actual_cost_usd, 5),
        'charged_usd': round(charged_usd, 4),
        'scenes': metadata.get('scenes_done', 0),
        'videos': metadata.get('video_count', 0),
        'images': metadata.get('image_count', 0),
        'duration_s': metadata.get('total_duration', 0),
    })


def get_usage(username=None, limit=100):
    q = {'username': username.strip().lower()} if username else {}
    rows = list(get_db().usage.find(q, {'_id': 0}).sort('ts', DESCENDING).limit(limit))
    return rows


def totals():
    """Aggregate spend across all users: actual API cost vs charged."""
    pipeline = [{'$group': {
        '_id': None,
        'actual': {'$sum': '$actual_cost_usd'},
        'charged': {'$sum': '$charged_usd'},
        'runs': {'$sum': 1},
    }}]
    r = list(get_db().usage.aggregate(pipeline))
    if not r:
        return {'actual': 0.0, 'charged': 0.0, 'runs': 0}
    return {'actual': round(r[0]['actual'], 4),
            'charged': round(r[0]['charged'], 4),
            'runs': r[0]['runs']}


# ── Settings (API keys + markup) ─────────────────────────────────────────────

def get_settings():
    doc = get_db().settings.find_one({'_id': 'config'}) or {}
    return {
        'claude_key': doc.get('claude_key') or os.environ.get('CLAUDE_API_KEY', ''),
        'pexels_key': doc.get('pexels_key') or os.environ.get('PEXELS_API_KEY', ''),
        'markup': float(doc.get('markup', DEFAULT_MARKUP)),
    }


def update_settings(claude_key=None, pexels_key=None, markup=None):
    updates = {}
    if claude_key is not None and claude_key.strip():
        updates['claude_key'] = claude_key.strip()
    if pexels_key is not None and pexels_key.strip():
        updates['pexels_key'] = pexels_key.strip()
    if markup is not None:
        updates['markup'] = max(1.0, float(markup))
    if updates:
        get_db().settings.update_one({'_id': 'config'}, {'$set': updates}, upsert=True)
