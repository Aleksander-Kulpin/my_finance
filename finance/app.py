import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Check user's available cash
    available_cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = available_cash_row[0]["cash"]

    # Get the information about number of shares grouped by companies owned by current user
    agg_rows = db.execute("SELECT symbol, SUM(qty) as sum_qty FROM history WHERE user_id = ? GROUP BY symbol",
                          session["user_id"])

    # Initialise grand total
    grand_total = cash

    # Initialise list of dictionaries for info about each company
    information = []

    # Get the information about shares grouped by companies
    for row in agg_rows:

        # Initialise vocabulary for each row
        current_row = {}

        # Get symbol
        current_row["symbol"] = row["symbol"]

        # Get a number of shares
        current_row["qty_shares"] = row["sum_qty"]

        # Get company name
        companies_row = db.execute("SELECT name FROM companies WHERE symbol = ?", row["symbol"])
        current_row["company_name"] = companies_row[0]['name']

        # Get the information about current price
        info = lookup(current_row["symbol"])
        current_row["current_price"] = info["price"]

        # Calculate totals
        current_row['total'] = current_row['qty_shares'] * current_row['current_price']
        grand_total += current_row['total']
        current_row["total"] = usd(current_row["total"])
        information.append(current_row)

    # Provide with the information for each row
    cash = usd(cash)
    grand_total = usd(grand_total)
    return render_template("index.html", information=information, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure that length of symbol is 4 letters
        if not (len(request.form.get("symbol")) == 4) or not request.form.get("symbol").isalpha():
            return apology("must provide 4 letters", 400)

        # Ensure quantity of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # Ensure quantity of shares is a positive integer
        try:
            qty_shares = int(request.form.get("shares"))
            if not qty_shares > 0:
                return apology("must provide a positive number of shares", 400)
        except ValueError:
            return apology("number of shares is not an integer", 400)

        # Lookup the current price
        information = lookup(request.form.get("symbol"))
        if information == None:
            return apology("invalid stock symbol", 400)
        else:
            current_price = float(information['price'])

        # Check user's available cash
        available_cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = float(available_cash_row[0]["cash"])
        if available_cash < current_price * qty_shares:
            return apology("you cannot afford the number of shares at the current price", 400)

        # Get current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Register purchase
        symbol = request.form.get("symbol").upper()
        db.execute("INSERT INTO history (user_id, date, activity, symbol, price, qty) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], dt_string, 'Purchase', symbol, current_price, qty_shares)

        # Check if the company is in the database and if so add it
        list_firms = db.execute("SELECT name FROM companies WHERE symbol = ?", symbol)
        if len(list_firms) == 0:
            db.execute("INSERT INTO companies (symbol, name) VALUES(?, ?)", symbol, information['name'])

        # Change user's cash balance
        payment = qty_shares * current_price
        cash_balance = available_cash - payment
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_balance, session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Get the information from database
    history_rows = db.execute("SELECT date, activity, symbol, price, qty FROM history WHERE user_id = ?", session["user_id"])

    # Provide with information
    return render_template("history.html", history_rows=history_rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure that length of symbol is 4 letters
        if not len(request.form.get("symbol")) == 4 or not request.form.get("symbol").isalpha():
            return apology("must provide 4 letters", 400)

        # Provide with information
        information = lookup(request.form.get("symbol"))
        if information == None:
            return apology("invalid stock symbol", 400)
        else:
            information['price'] = usd(information['price'])
            return render_template("quoted.html", information=information)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was repeated correctly
        elif not (request.form.get("password") == request.form.get("confirmation")):
            return apology("passwords are not same", 400)

        # Ensure that length of the new password at least 6 symbols
        if not (len(request.form.get("password")) >= 6):
            return apology("length of the password must be at least 6 symbols", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username has not been created before
        if len(rows) != 0:
            return apology("username already exists", 400)

        # Remember registrant
        name = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", name, hash)

        # Confirm registration
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Get the information about number of shares grouped by companies owned by current user
    agg_rows = db.execute("SELECT symbol, SUM(qty) as sum_qty FROM history WHERE user_id = ? GROUP BY symbol",
                          session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure that length of symbol is 4 letters
        if not len(request.form.get("symbol")) == 4 or not request.form.get("symbol").isalpha():
            return apology("must provide 4 letters", 400)

        # Ensure quantity of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # Ensure quantity of shares is a positive integer
        try:
            qty_shares = int(request.form.get("shares"))
            if not qty_shares > 0:
                return apology("must provide a positive number of shares", 400)
        except ValueError:
            return apology("number of shares is not an integer", 400)

        # Lookup the current price
        symbol = request.form.get("symbol").upper()
        information = lookup(symbol)
        if information == None:
            return apology("invalid stock symbol", 400)
        else:
            current_price = float(information['price'])

        # Check user's available shares
        available_shares_row = db.execute("SELECT symbol, SUM(qty) as sum_qty FROM history WHERE user_id = ? AND symbol = ? GROUP BY symbol",
                                          session["user_id"], symbol)
        available_shares = available_shares_row[0]['sum_qty']
        if available_shares < qty_shares:
            return apology("you do not have this number of shares", 400)

        # Get currect date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Register the sale
        db.execute("INSERT INTO history (user_id, date, activity, symbol, price, qty) VALUES(?, ?, ?, ?, ?, ?)",
                   session["user_id"], dt_string, 'Sale', symbol, current_price, qty_shares*(-1))

        # Change user's cash balance
        payment = qty_shares * current_price
        available_cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = available_cash_row[0]['cash']
        cash_balance = available_cash + payment
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_balance, session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html", list_symbols=agg_rows)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_money():
    """Increase currect user's cash balance"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure amount of money was submitted
        if not request.form.get("money"):
            return apology("must provide amount of money", 400)

        # Ensure amount of money is a positive integer
        inflow = int(request.form.get("money"))
        try:
            inflow = int(request.form.get("money"))
            if not inflow > 0:
                return apology("must provide a positive amount", 400)
        except ValueError:
            return apology("amount is not an integer", 400)

        # Check user's available cash
        available_cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        available_cash = float(available_cash_row[0]["cash"])

        # Get current date and time
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        # Register cash inflow
        db.execute("INSERT INTO cash_account (user_id, date, activity, amount) VALUES(?, ?, ?, ?)",
                   session["user_id"], dt_string, 'Top up', inflow)

        # Change user's cash balance
        cash_balance = available_cash + inflow
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_balance, session["user_id"])

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("add.html")


@app.route("/change", methods=["GET", "POST"])
@login_required
def change_password():
    """Change current user's password"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure old password was submitted
        if not request.form.get("old_password"):
            return apology("must provide username", 400)

        # Ensure old password is correct
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(rows[0]["hash"], request.form.get("old_password")):
            return apology("old password is not correct", 400)

        # Ensure new password was submitted
        if not request.form.get("new_password"):
            return apology("must provide a new password", 400)

        # Ensure password was repeated correctly
        if not (request.form.get("new_password") == request.form.get("confirmation")):
            return apology("new passwords are not same", 400)

        # Ensure that length of the new password at least 6 symbols
        if not (len(request.form.get("new_password")) >= 6):
            return apology("length of the cd password must be at least 6 symbols", 400)

        # Remember new password
        hash = generate_password_hash(request.form.get("new_password"))
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, session["user_id"])

        # Confirm registration
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change.html")