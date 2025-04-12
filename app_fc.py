from flask_cors import CORS
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__ , template_folder=BASE_DIR)
app.secret_key = 'your_secret_key'  # Replace with a secure key

MONGO_USER = os.getenv("MONGO_USER", "Srikar")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "One_Piece")
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DB = os.getenv("MONGO_DB", "expense_tracker")

MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"

client = MongoClient(MONGO_URI)
db = client["expense_tracker"]
users_collection = db["users"]
budgets_collection = db["budgets"]  # New collection for budgets and expenses
expenses_collection = db["expenses"]

@app.route("/", methods=["GET"])
def serve_frontend():
    return render_template("index.html")

@app.route('/dashboard')
def dashboard():
    print("Session:", session.get('user'))
    if 'user' not in session:
        return redirect(url_for('serve_frontend'))
    return render_template('dashboard.html')

@app.route('/api/login', methods=['POST'])
def login():
    credentials = request.get_json()
    email = credentials.get('email')
    password = credentials.get('password')
    user = users_collection.find_one({"email": email})
    if user and check_password_hash(user["password"], password):
        session['user'] = email
        print("Login successful for:", email)
        return jsonify({"status": "success", "message": "Login successful!", "redirect": "/dashboard"})
    return jsonify({"status": "error", "message": "Invalid credentials."}), 401

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if users_collection.find_one({"email": email}):
        return jsonify({"error": "User already exists"}), 400
    hashed_password = generate_password_hash(password)
    users_collection.insert_one({"username": username, "email": email, "password": hashed_password})
    # Initialize budget document for new user
    budgets_collection.insert_one({"user_email": email, "budget": 0.0, "expenses": []})
    return jsonify({"message": "Signup successful"}), 201

@app.route('/api/data', methods=['GET'])
def get_data():
    if 'user' not in session:
        return jsonify({"message": "Unauthorized", "status": "error"}), 401
    user_email = session['user']
    data = budgets_collection.find_one({"user_email": user_email})
    if not data:
        # Initialize if not found (shouldn’t happen post-signup, but as a fallback)
        budgets_collection.insert_one({"user_email": user_email, "budget": 0.0, "expenses": []})
        data = {"user_email": user_email, "budget": 0.0, "expenses": []}
    return jsonify({"budget": data["budget"], "expenses": data["expenses"]})

@app.route('/api/budget', methods=['POST'])
def update_budget():
    if 'user' not in session:
        return jsonify({"message": "Unauthorized", "status": "error"}), 401
    user_email = session['user']
    data = request.json
    new_budget = float(data.get('budget', 0))  # Amount to add
    # Update by adding to existing budget
    budgets_collection.update_one(
        {"user_email": user_email},
        {"$inc": {"budget": new_budget}},  # Increment budget
        upsert=True  # Create if not exists
    )
    updated_data = budgets_collection.find_one({"user_email": user_email})
    return jsonify({"message": "Budget updated", "budget": updated_data["budget"]})

@app.route('/api/expense', methods=['POST'])
def add_expense():
    if 'user' not in session:
        return jsonify({"message": "Unauthorized", "status": "error"}), 401
    
    user_email = session['user']
    data = request.json
    expense_name = data.get('name')
    expense_amount = float(data.get('amount', 0))

    print(f"Received expense: name={expense_name}, amount={expense_amount}")

    if expense_name and expense_amount > 0:
        # Insert the expense as a new document in expenses_collection
        expense_doc = {
            "user_email": user_email,
            "name": expense_name,
            "amount": expense_amount
        }
        inserted_id = expenses_collection.insert_one(expense_doc).inserted_id
        
        print(f"Expense added with ID: {inserted_id}")
        
        return jsonify({"message": "Expense added", "expense_id": str(inserted_id)}), 201

    print("Invalid input: skipping update")
    return jsonify({"message": "Invalid input"}), 400

@app.route('/api/expense/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    if 'user' not in session:
        return jsonify({"message": "Unauthorized", "status": "error"}), 401

    user_email = session['user']

    try:
        result = expenses_collection.delete_one({"_id": ObjectId(expense_id), "user_email": user_email})
        
        if result.deleted_count == 0:
            return jsonify({"message": "Expense not found or unauthorized"}), 404

        print(f"Deleted expense ID: {expense_id}")
        return jsonify({"message": "Expense deleted"}), 200

    except Exception as e:
        print(f"Error deleting expense: {e}")
        return jsonify({"message": "Invalid Expense ID"}), 400

@app.route('/api/reset', methods=['POST'])
def reset_data():
    if 'user' not in session:
        return jsonify({"message": "Unauthorized", "status": "error"}), 401
    user_email = session['user']
    budgets_collection.update_one(
        {"user_email": user_email},
        {"$set": {"budget": 0.0, "expenses": []}}
    )
    return jsonify({"message": "Data reset successfully", "status": "success"})

@app.route('/logout', methods=['GET', 'POST'])  # Allow both GET and POST
def logout():
    session.pop('user', None)
    return render_template("index.html")  # Ensure login.html exists

if __name__ == "__main__":
    app.run(debug=True)
