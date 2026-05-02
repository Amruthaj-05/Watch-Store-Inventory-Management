from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "mysecretkey123"

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL)''')

    # Insert default admin
    c.execute("SELECT * FROM users WHERE username=?", ("watch",))
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("watch", "shop7090"))

    # Customers table
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT)''')

    # Inventory table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL)''')

    # Sales table
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    watch_id INTEGER,
                    quantity INTEGER,
                    total_price REAL,
                    date TEXT,
                    FOREIGN KEY(customer_id) REFERENCES customers(id),
                    FOREIGN KEY(watch_id) REFERENCES inventory(id))''')

    conn.commit()
    conn.close()

init_db()

# ---------- Context processor ----------
@app.context_processor
def inject_user():
    return dict(user=session.get("user"))

# ---------- Helper: Require Login ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Login Route ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))  # already logged in

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user"] = username
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html", active_page="login")

# ---------- Logout Route ----------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# ---------- Routes ----------
@app.route("/")
@login_required
def index():
    return render_template("index.html", active_page="home")

# ----- Customers -----
@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        c.execute("INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)", (name, phone, email))
        conn.commit()

    c.execute("SELECT * FROM customers")
    cust_list = c.fetchall()
    conn.close()
    return render_template("customers.html", customers=cust_list, active_page="customers")

# ----- Inventory -----
@app.route("/inventory", methods=["GET", "POST"])
@login_required
def inventory():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        c.execute("INSERT INTO inventory (name, price, quantity) VALUES (?, ?, ?)", (name, price, quantity))
        conn.commit()

    c.execute("SELECT * FROM inventory")
    items = c.fetchall()
    conn.close()
    return render_template("inventory.html", inventory=items, active_page="inventory")

# ----- Sales -----
@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        customer_id = int(request.form["customer_id"])
        watch_id = int(request.form["watch_id"])
        quantity = int(request.form["quantity"])

        c.execute("SELECT price, quantity FROM inventory WHERE id=?", (watch_id,))
        watch = c.fetchone()
        if not watch or quantity > watch[1]:
            conn.close()
            return render_template("no_stock.html", watch_id=watch_id, requested=quantity, available=watch[1] if watch else 0)

        total_price = watch[0] * quantity
        c.execute("INSERT INTO sales (customer_id, watch_id, quantity, total_price, date) VALUES (?, ?, ?, ?, ?)",
                  (customer_id, watch_id, quantity, total_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE id=?", (quantity, watch_id))
        conn.commit()

    # Fetch sales
    c.execute("""SELECT sales.id, customers.name, inventory.name, sales.quantity, sales.total_price, sales.date
                 FROM sales
                 JOIN customers ON sales.customer_id = customers.id
                 JOIN inventory ON sales.watch_id = inventory.id
                 ORDER BY sales.date DESC""")
    sales_data = c.fetchall()

    # Fetch dropdowns
    c.execute("SELECT * FROM customers")
    customers = c.fetchall()
    c.execute("SELECT * FROM inventory")
    inventory = c.fetchall()
    conn.close()

    return render_template("sales.html", sales=sales_data, customers=customers, inventory=inventory, active_page="sales")

# ----- Report -----
@app.route("/report", methods=["GET", "POST"])
@login_required
def report():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        c.execute("""SELECT sales.id, customers.name, inventory.name, sales.quantity, sales.total_price, sales.date
                     FROM sales
                     JOIN customers ON sales.customer_id = customers.id
                     JOIN inventory ON sales.watch_id = inventory.id
                     WHERE date BETWEEN ? AND ?
                     ORDER BY sales.date DESC""",
                  (start_date + " 00:00:00", end_date + " 23:59:59"))
    else:
        c.execute("""SELECT sales.id, customers.name, inventory.name, sales.quantity, sales.total_price, sales.date
                     FROM sales
                     JOIN customers ON sales.customer_id = customers.id
                     JOIN inventory ON sales.watch_id = inventory.id
                     ORDER BY sales.date DESC""")

    report_data = c.fetchall()
    conn.close()
    return render_template("report.html", report=report_data, active_page="report")

# ----- Edit Inventory -----
@app.route("/inventory/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_inventory(id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        c.execute("UPDATE inventory SET name=?, price=?, quantity=? WHERE id=?", (name, price, quantity, id))
        conn.commit()
        conn.close()
        return redirect("/inventory")

    c.execute("SELECT * FROM inventory WHERE id=?", (id,))
    item = c.fetchone()
    conn.close()
    return render_template("edit_inventory.html", item=item, active_page="inventory")

# ----- Edit Customer -----
@app.route("/customers/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_customer(id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        c.execute("UPDATE customers SET name=?, phone=?, email=? WHERE id=?", (name, phone, email, id))
        conn.commit()
        conn.close()
        return redirect("/customers")

    c.execute("SELECT * FROM customers WHERE id=?", (id,))
    customer = c.fetchone()
    conn.close()
    return render_template("edit_customer.html", customer=customer, active_page="customers")

# ----- Edit Sale -----
@app.route("/sales/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_sale(id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        customer_id = int(request.form["customer_id"])
        watch_id = int(request.form["watch_id"])
        quantity = int(request.form["quantity"])

        # Restore old inventory first
        c.execute("SELECT watch_id, quantity FROM sales WHERE id=?", (id,))
        old_watch_id, old_quantity = c.fetchone()
        c.execute("UPDATE inventory SET quantity = quantity + ? WHERE id=?", (old_quantity, old_watch_id))

        # Check new stock
        c.execute("SELECT quantity, price FROM inventory WHERE id=?", (watch_id,))
        watch = c.fetchone()
        if not watch or quantity > watch[0]:
            conn.close()
            return render_template("no_stock.html", watch_id=watch_id, requested=quantity, available=watch[0] if watch else 0)

        # Update sale
        total_price = quantity * watch[1]
        c.execute("UPDATE sales SET customer_id=?, watch_id=?, quantity=?, total_price=? WHERE id=?",
                  (customer_id, watch_id, quantity, total_price, id))
        c.execute("UPDATE inventory SET quantity = quantity - ? WHERE id=?", (quantity, watch_id))

        conn.commit()
        conn.close()
        return redirect("/sales")

    # Fetch sale + dropdowns
    c.execute("SELECT * FROM sales WHERE id=?", (id,))
    sale = c.fetchone()
    c.execute("SELECT * FROM customers")
    customers = c.fetchall()
    c.execute("SELECT * FROM inventory")
    inventory = c.fetchall()
    conn.close()

    return render_template("edit_sale.html", sale=sale, customers=customers, inventory=inventory, active_page="sales")

import webbrowser
import threading
if __name__ == "__main__":
    init_db()
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=True, use_reloader=False)
