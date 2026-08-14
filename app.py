from flask import Flask, render_template, request, redirect, session
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "smart-farmer-secret-key-change-this"


# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect("farm_expenses.db")
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    conn = get_db()

    # Users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Expenses
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT
        )
    """)

    # Income
    conn.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT
        )
    """)

    # Budgets
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            month TEXT NOT NULL,
            amount REAL NOT NULL
        )
    """)

    conn.commit()

    # Add user_id to old tables if necessary
    for table in ["expenses", "income", "budgets"]:

        columns = conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        column_names = [column["name"] for column in columns]

        if "user_id" not in column_names:

            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
            )

    conn.commit()
    conn.close()


# ================= LOGIN CHECK =================

def logged_in():

    return "user_id" in session


# ================= SIGNUP =================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:

            conn.close()

            return render_template(
                "signup.html",
                error="An account with this email already exists."
            )

        hashed_password = generate_password_hash(password)

        conn.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, hashed_password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template("login.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= DASHBOARD =================

@app.route("/")
def home():

    if not logged_in():
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    total_expenses = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["total"]

    total_income = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM income
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()["total"]

    categories = [
        "Seeds",
        "Fertilizers",
        "Pesticides",
        "Labour",
        "Fuel",
        "Machinery"
    ]

    category_expenses = {}

    for category in categories:

        result = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = ?
            AND category = ?
            """,
            (user_id, category)
        ).fetchone()

        category_expenses[category] = result["total"]

    conn.close()

    profit = total_income - total_expenses

    return render_template(
        "index.html",
        total_income=total_income,
        total_expenses=total_expenses,
        profit=profit,
        category_expenses=category_expenses,
        user_name=session.get("user_name")
    )


# ================= ADD EXPENSE =================

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if not logged_in():
        return redirect("/login")

    if request.method == "POST":

        amount = request.form.get("amount")
        category = request.form.get("category")
        date = request.form.get("date")
        description = request.form.get("description")

        conn = get_db()

        conn.execute(
            """
            INSERT INTO expenses
            (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                amount,
                category,
                date,
                description
            )
        )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add_expense.html")


# ================= ADD INCOME =================

@app.route("/add-income", methods=["GET", "POST"])
def add_income():

    if not logged_in():
        return redirect("/login")

    if request.method == "POST":

        amount = request.form.get("amount")
        source = request.form.get("source")
        date = request.form.get("date")
        description = request.form.get("description")

        conn = get_db()

        conn.execute(
            """
            INSERT INTO income
            (user_id, amount, source, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                amount,
                source,
                date,
                description
            )
        )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add_income.html")


# ================= TRANSACTIONS =================

@app.route("/transactions")
def transactions():

    if not logged_in():
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    expenses = conn.execute(
        """
        SELECT
            id,
            date,
            'Expense' AS type,
            category,
            amount,
            description
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    income = conn.execute(
        """
        SELECT
            id,
            date,
            'Income' AS type,
            source AS category,
            amount,
            description
        FROM income
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    transactions = list(expenses) + list(income)

    transactions.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return render_template(
        "transactions.html",
        transactions=transactions
    )


# ================= EDIT EXPENSE =================

@app.route("/edit-expense/<int:id>", methods=["GET", "POST"])
def edit_expense(id):

    if not logged_in():
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        amount = request.form.get("amount")
        category = request.form.get("category")
        date = request.form.get("date")
        description = request.form.get("description")

        conn.execute(
            """
            UPDATE expenses
            SET amount = ?,
                category = ?,
                date = ?,
                description = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                amount,
                category,
                date,
                description,
                id,
                user_id
            )
        )

        conn.commit()
        conn.close()

        return redirect("/transactions")

    expense = conn.execute(
        """
        SELECT *
        FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (id, user_id)
    ).fetchone()

    conn.close()

    if expense is None:
        return "Expense not found", 404

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# ================= EDIT INCOME =================

@app.route("/edit-income/<int:id>", methods=["GET", "POST"])
def edit_income(id):

    if not logged_in():
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        amount = request.form.get("amount")
        source = request.form.get("source")
        date = request.form.get("date")
        description = request.form.get("description")

        conn.execute(
            """
            UPDATE income
            SET amount = ?,
                source = ?,
                date = ?,
                description = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                amount,
                source,
                date,
                description,
                id,
                user_id
            )
        )

        conn.commit()
        conn.close()

        return redirect("/transactions")

    income = conn.execute(
        """
        SELECT *
        FROM income
        WHERE id = ?
        AND user_id = ?
        """,
        (id, user_id)
    ).fetchone()

    conn.close()

    if income is None:
        return "Income not found", 404

    return render_template(
        "edit_income.html",
        income=income
    )


# ================= DELETE EXPENSE =================

@app.route("/delete-expense/<int:id>")
def delete_expense(id):

    if not logged_in():
        return redirect("/login")

    conn = get_db()

    conn.execute(
        """
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/transactions")


# ================= DELETE INCOME =================

@app.route("/delete-income/<int:id>")
def delete_income(id):

    if not logged_in():
        return redirect("/login")

    conn = get_db()

    conn.execute(
        """
        DELETE FROM income
        WHERE id = ?
        AND user_id = ?
        """,
        (id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/transactions")


# ================= BUDGET =================

@app.route("/budget", methods=["GET", "POST"])
def budget():

    if not logged_in():
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        category = request.form.get("category")
        month = request.form.get("month")
        amount = request.form.get("amount")

        existing = conn.execute(
            """
            SELECT id
            FROM budgets
            WHERE user_id = ?
            AND category = ?
            AND month = ?
            """,
            (
                user_id,
                category,
                month
            )
        ).fetchone()

        if existing:

            conn.execute(
                """
                UPDATE budgets
                SET amount = ?
                WHERE id = ?
                AND user_id = ?
                """,
                (
                    amount,
                    existing["id"],
                    user_id
                )
            )

        else:

            conn.execute(
                """
                INSERT INTO budgets
                (user_id, category, month, amount)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    category,
                    month,
                    amount
                )
            )

        conn.commit()

    budgets = conn.execute(
        """
        SELECT *
        FROM budgets
        WHERE user_id = ?
        ORDER BY month DESC, category
        """,
        (user_id,)
    ).fetchall()

    budget_data = []

    for budget in budgets:

        spent = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = ?
            AND category = ?
            AND substr(date, 1, 7) = ?
            """,
            (
                user_id,
                budget["category"],
                budget["month"]
            )
        ).fetchone()["total"]

        budget_amount = budget["amount"]

        remaining = budget_amount - spent

        if budget_amount > 0:
            percentage = (spent / budget_amount) * 100
        else:
            percentage = 0

        if percentage >= 100:
            status = "exceeded"
        elif percentage >= 80:
            status = "warning"
        else:
            status = "safe"

        budget_data.append({
            "id": budget["id"],
            "category": budget["category"],
            "month": budget["month"],
            "amount": budget_amount,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage,
            "status": status
        })

    conn.close()

    return render_template(
        "budget.html",
        budgets=budget_data
    )


# ================= START =================

# ==================== START APPLICATION ====================

# Create the database and all required tables when the app starts.
# This is important for both local Flask and Render/Gunicorn.
create_database()


if __name__ == "__main__":
    app.run(debug=True)