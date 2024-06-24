from web import create_app, db

app = create_app()

# Create the tables in the database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

