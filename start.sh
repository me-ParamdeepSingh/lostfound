#!/usr/bin/env bash
set -o errexit

# Run database migrations on container start
echo "==> Running database migrations..."
python manage.py migrate --no-input

# Ensure admin superuser is available
python manage.py shell -c "
try:
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@lostfound.com', 'admin123')
        print('✅ Created default admin superuser (admin / admin123)')
except Exception as e:
    print(f'Superuser setup notice: {e}')
" || true

echo "==> Starting Gunicorn server..."
exec gunicorn lostfound.wsgi:application
