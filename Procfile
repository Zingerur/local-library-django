web: python manage.py migrate && python manage.py collectstatic --noinput && python manage.py shell < locallibrary/create_superuser.py && gunicorn locallibrary.wsgi

