from flask import Flask, render_template, request, redirect, url_for, session, abort, flash, g
from peewee import *
from functools import wraps
from hashlib import md5
import secrets
import geopy.distance

db = SqliteDatabase('data.db')

class Businesses(Model):
    busername = CharField(unique=True)
    bpassword = CharField()
    businessname = CharField()
    offer = CharField()
    longitude = DecimalField()
    latitude = DecimalField()

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
    session["username"] = user.cusername
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

@app.route("/", methods=['GET','POST'])
def home():
    if request.method == 'GET':
        return render_template("homepage.html")
    
    if request.method == 'POST':
        data = dict(request.form)
        print(data)
        stores = Businesses.select()
        results = []
        for store in stores:
            store.distance = geopy.distance.geodesic((store.longitude,store.latitude), (float(data["longitude"]),float(data["latitude"]))).miles
            results.append(store)
        results.sort(key=lambda store: store.distance)
        return render_template("homepage.html",data=results)


@app.route("/data")
def get_stores():
    stores = Businesses.select()
    customers = Customers.select()
    punchcards = PunchCards.select().join(Customers).switch(PunchCards).join(Businesses)

    return render_template("stores.html", stores=stores, customers=customers,punchcards=punchcards)

@app.route("/business/signup", methods=['GET', 'POST'])
def business_signup():
    if request.method == 'GET':
        return render_template("business_signup.html")
    
    if request.method == 'POST':
        data = dict(request.form)
        try:
            with db.atomic():
                user = Businesses.create(
                    busername=data["username"],
                    bpassword=md5((data["password"]).encode('utf-8')).hexdigest(),
                    businessname = data["businessname"],
                    offer=data["offer"],
                    longitude = data["longitude"],
                    latitude = data["latitude"])
                auth_business(user)
                return redirect(url_for('punch'))
        except IntegrityError:
            flash("That username is already taken")
    
    return render_template("business_signup.html")
    
@app.route("/business/update", methods=['GET', 'POST'])
def business_update():
    user = Businesses.get(Businesses.id == session["user_id"])

    if request.method == 'GET':
        return render_template("business_update.html", user=user, name=session["username"])
    
    if request.method == 'POST':
        data = dict(request.form)
        try:
            query = Businesses.update(
                busername=data["username"],
                bpassword=md5((data["password"]).encode('utf-8')).hexdigest(),
                businessname = data["businessname"],
                offer=data["offer"],
                longitude = data["longitude"],
                latitude = data["latitude"]).where(Businesses.id == session["user_id"])
            query.execute()
            user = Businesses.get(Businesses.busername == data["username"])
            auth_business(user)
            return redirect(url_for('punch'))
        except IntegrityError:
            flash("Username taken")

    return render_template("business_update.html", user=user, name=session["username"])

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
        try:
            user = Customers.create(
                cusername=data["username"],
                cpassword=md5((data["password"]).encode('utf-8')).hexdigest())
            auth_customer(user)
            return redirect(url_for('customer_punches'))
        except IntegrityError:
            flash("Username taken")

@app.route("/customer/update", methods=['GET', 'POST'])
def customer_update():

    if request.method == 'GET':
        return render_template("customer_update.html",name=session["username"])
    
    if request.method == 'POST':
        data = dict(request.form)
        try:
            query = Customers.update(
                cusername=data["username"],
                cpassword=md5((data["password"]).encode('utf-8')).hexdigest())
            user = Customers.get(Customers.id == session["user_id"])
            auth_customer(user)
            return redirect(url_for('customer_punches'))
        except IntegrityError:
            flash("Username taken")

    return render_template("customer_update.html",name=session["username"])

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
            return redirect(url_for("customer_punches"))

    return render_template("customer_signin.html")

@app.route("/business/punch",methods=['GET','POST'])
@business_required
def punch():
    if request.method == 'GET':
        return render_template("business_punch.html",name=session["username"])
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
                if punchcard.punches >= 9:
                    query = PunchCards.update(punches=0).where(PunchCards.id == punchcard.id)
                    message = "Punchcard completed!"
                else:
                    query = PunchCards.update(punches=PunchCards.punches+1).where(PunchCards.id == punchcard.id)
                    message = str(9-punchcard.punches) + " punches until prize!"
                query.execute()
                return render_template("business_punch.html", message = message, name=session["username"])

    return render_template("business_punch.html",message = "Nothing")

@app.route("/customer/punches", methods=['GET','POST'])
def customer_punches():
    if request.method == 'GET':
        return render_template("customer_punches.html",name=session["username"])
    
    if request.method == 'POST':
        data = dict(request.form)
        print(data)
        stores = PunchCards.select().join(Businesses).switch(PunchCards).join(Customers).where(Customers.id == session["user_id"])
        results = []
        for store in stores:
            store.distance = geopy.distance.geodesic((store.business.longitude,store.business.latitude), (float(data["longitude"]),float(data["latitude"]))).miles
            print(store.punches)
            results.append(store)
        results.sort(key=lambda store: store.distance)
        return render_template("customer_punches.html",data=results,name=session["username"])

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)