# 1) Create + activate virtual env
python3 -m venv .venv
source .venv/bin/activate

# 2) Install dependencies used by this project
pip install -r requirements.txt

# 3) Run migrations
python manage.py migrate

# 4) Start server
python manage.py runserver

# 5) (Optional) create admin user
python manage.py createsuperuser