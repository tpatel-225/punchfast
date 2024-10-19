from flask import Flask, render_template, request, redirect, url_for, session, abort, flash, g
from peewee import *
from functools import wraps
from hashlib import md5
import secrets


db = SqliteDatabase('data.db')

class Businesses(Model):
    busername = CharField(unique=True)
    bpassword = CharField()
    offer = CharField()

    class Meta:
        database = db

class Customers(Model):
    cusername = CharField(unique=True)
    cpassword = CharField()

    class Meta:
        database = db

class PunchCards(Model):
    business = ForeignKeyField(Businesses, backref="username")
    customer = ForeignKeyField(Customers, backref="username")
    punches = IntegerField()

    class Meta:
        database = db

db.connect()
db.create_tables([Businesses, Customers, PunchCards])

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(16)


def auth_business(user):
    session["logged_in"] = True
    session["user_id"] = user.id
    session["username"] = user.busername
    session["business"] = True

def auth_customer(user):
    session["logged_in"] = True
    session["user_id"] = user.id
    session["username"] = user.busername
    session["business"] = False

def business_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get("logged_in") and not session.get("business"):
            return redirect(url_for("business_signin"))
        return f(*args, **kwargs)
    return inner

def customer_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not session.get("logged_in") and session.get("business"):
            return redirect(url_for("customer_signin"))
        return f(*args, **kwargs)
    return inner

@app.route("/")
@app.route("/stores")
def get_stores():
    stores = Businesses.select()
    customers = Customers.select()
    punchcards = PunchCards.select().join(Customers).switch(PunchCards).join(Businesses)
    print(punchcards)

    return render_template("stores.html", stores=stores, customers=customers,punchcards=punchcards)

# Create a new pet with a dropdown to select kind
@app.route("/business/signup", methods=['GET', 'POST'])
def business_signup():
    if request.method == 'GET':
        return render_template("business_signup.html")
    
    if request.method == 'POST':
        data = dict(request.form)
        Businesses.create(
            busername=data["username"],
            bpassword=md5((data["password"]).encode('utf-8')).hexdigest(),
            offer=data["offer"])
        return redirect(url_for('get_stores'))

@app.route("/business/signin", methods=['GET', 'POST'])
def business_signin():
    if request.method == 'GET':
        return render_template("business_signin.html")
    
    if request.method == 'POST' and request.form["username"]:
        try:
            pw_hash = md5(request.form["password"].encode("utf-8")).hexdigest()
            user = Businesses.get(
                (Businesses.busername == request.form["username"]) &
                (Businesses.bpassword == pw_hash))
        except Businesses.DoesNotExist:
            flash("The password entered in incorrect")
        else:
            auth_business(user)
            return redirect(url_for("punch"))

    return render_template("business_signin.html")

@app.route("/customer/signup", methods=['GET', 'POST'])
def customer_signup():
    if request.method == 'GET':
        return render_template("customer_signup.html")
    
    if request.method == 'POST':
        data = dict(request.form)
        Customers.create(
            cusername=data["username"],
            cpassword=md5((data["password"]).encode('utf-8')).hexdigest())
        return redirect(url_for('get_stores'))

@app.route("/customer/signin", methods=['GET', 'POST'])
def customer_signin():
    if request.method == 'GET':
        return render_template("customer_signin.html")
    
    if request.method == 'POST' and request.form["username"]:
        try:
            pw_hash = md5(request.form["password"].encode("utf-8")).hexdigest()
            user = Customers.get(
                (Customers.cusername == request.form["username"]) &
                (Customers.cpassword == pw_hash))
        except Customers.DoesNotExist:
            flash("The password entered in incorrect")
        else:
            auth_customer(user)
            return redirect(url_for("get_stores"))

    return render_template("customer_signin.html")

@app.route("/business/punch",methods=['GET','POST'])
@business_required
def punch():
    if request.method == 'GET':
        return render_template("business_punch.html")
    if request.method == 'POST' and request.form["username"]:
        try:
            customer = Customers.get(Customers.cusername == request.form["username"])
        except Customers.DoesNotExist:
            return render_template("business_punch.html",message = "Customer doesn't exist")
        else:
            try:
                punchcard = PunchCards.get(
                    (PunchCards.customer == customer.id)
                    & (PunchCards.business == session["user_id"]))
            except PunchCards.DoesNotExist:
                me = Businesses.get(Businesses.id == session["user_id"])
                PunchCards.create(business = me, customer = customer, punches = 1)
                return render_template("business_punch.html",message = "New punch card made")

            else:
                query = PunchCards.update(punches=PunchCards.punches+1).where(PunchCards.id == punchcard.id)
                query.execute()
                return render_template("business_punch.html",message = punchcard.punches)

    return render_template("business_punch.html",message = "Nothing")



if __name__ == "__main__":
    app.run(debug=True)