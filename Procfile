release: python manage.py migrate
web: gunicorn locallibrary.wsgi

release: python manage.py migrate && python manage.py shell < locallibrary/create_superuser.py
web: gunicorn locallibrary.wsgi
