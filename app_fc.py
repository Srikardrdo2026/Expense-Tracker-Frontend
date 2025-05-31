from flask_cors import CORS
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from bson.objectid import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "../frontend")  # Adjust as needed

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key_here")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://srikardrdo2026.github.io/Expense-Tracker-Frontend/")

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_CLUSTER = os.getenv("MONGO_CLUSTER")
MONGO_DB = os.getenv("MONGO_DB")

MONGO_URI = f"mongodb+srv://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_CLUSTER}/{MONGO_DB}?retryWrites=true&w=majority"

# Ensure sensitive environment variables are properly configured
if not all([MONGO_USER, MONGO_PASSWORD, MONGO_CLUSTER, MONGO_DB]):
    raise ValueError("MongoDB environment variables are not properly configured.")

try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
except Exception as e:
    raise ConnectionError(f"Failed to connect to MongoDB: {e}")

users_collection = db["users"]
budgets_collection = db["budgets"]
expenses_collection = db["expenses"]

# Allow CORS from your frontend URL only, with credentials support
CORS(app, supports_credentials=True, origins=[FRONTEND_URL])

# Improve session security
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Ensures cookies are sent over HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevents JavaScript access to cookies
)

@app.route("/", methods=["GET"])
def serve_frontend():
    # Redirect to your frontend hosted URL
    return redirect(FRONTEND_URL)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(FRONTEND_URL)
    # Optionally serve dashboard.html from backend if you want, else redirect
    return redirect(f"{FRONTEND_URL}dashboard.html")

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = users_collection.find_one({'username': username})
    if user and check_password_hash(user['password'], password):
        session['user'] = username
        return jsonify({'message': 'Logged in successfully'})
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(FRONTEND_URL)

@app.route('/api/data', methods=['GET'])
def get_data():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['user']
    budget_doc = budgets_collection.find_one({'username': username})
    budget = budget_doc['budget'] if budget_doc else 0

    expenses_cursor = expenses_collection.find({'username': username})
    expenses = [{
        '_id': str(e['_id']),
        'name': e['name'],
        'amount': e['amount']
    } for e in expenses_cursor]

    return jsonify({'budget': budget, 'expenses': expenses})

@app.route('/api/budget', methods=['POST'])
def add_budget():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['user']
    data = request.json
    budget = data.get('budget')
    if budget is None or budget < 0:
        return jsonify({'error': 'Invalid budget value'}), 400

    budgets_collection.update_one(
        {'username': username},
        {'$set': {'budget': budget}},
        upsert=True
    )
    return jsonify({'budget': budget})

@app.route('/api/expense', methods=['POST'])
def add_expense():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['user']
    data = request.json
    name = data.get('name')
    amount = data.get('amount')

    if not name or amount is None or amount <= 0:
        return jsonify({'error': 'Invalid expense data'}), 400

    expense = {
        'username': username,
        'name': name,
        'amount': amount
    }

    result = expenses_collection.insert_one(expense)
    return jsonify({'expense_id': str(result.inserted_id)})

@app.route('/api/expense/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['user']
    try:
        result = expenses_collection.delete_one({'_id': ObjectId(expense_id), 'username': username})
        if result.deleted_count == 0:
            return jsonify({'error': 'Expense not found'}), 404
        return jsonify({'message': 'Expense deleted'})
    except Exception:
        return jsonify({'error': 'Invalid expense ID'}), 400

@app.route('/api/reset', methods=['POST'])
def reset_data():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    username = session['user']

    budgets_collection.delete_one({'username': username})
    expenses_collection.delete_many({'username': username})

    return jsonify({'message': 'Data reset'})

if __name__ == "__main__":
    app.run(debug=True)