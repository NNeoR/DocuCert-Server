from flask_migrate import Migrate
from web import create_app, db

app = create_app()
migrate = Migrate(app, db)

# Create the tables in the database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)

