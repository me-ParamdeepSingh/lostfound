#!/usr/bin/env bash
# exit on error
set -o errexit

chmod +x start.sh build.sh || true

pip install -r requirements.txt

python manage.py collectstatic --no-input

# Run migrations on database
echo "==> Running PostgreSQL database migrations..."
python manage.py migrate --no-input

# Ensure default superuser exists
python manage.py shell -c "
try:
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@lostfound.com', 'admin123')
        print('✅ Default admin superuser ready')
except Exception as e:
    print(f'Note on admin creation: {e}')
"


