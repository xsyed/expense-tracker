# 1) Create + activate virtual env
python3 -m venv .venv
source .venv/bin/activate

# 2) Install dependencies used by this project
pip install --upgrade pip
pip install "Django>=4.2,<5" django-crispy-forms crispy-bootstrap5 python-dotenv

# 3) Run migrations
python manage.py migrate

# 4) (Optional) create admin user
python manage.py createsuperuser

# 5) Start server
python manage.py runserver