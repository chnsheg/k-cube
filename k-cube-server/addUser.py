from app.models import User
from app import db
u = User(email='test@example.com')
u.set_password('password123')
db.session.add(u)
db.session.commit()
exit()
