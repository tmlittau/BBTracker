#!/bin/sh
# Production backend entrypoint: apply migrations, gather static, optionally seed
# reference data, then hand off to gunicorn (PID 1 via exec).
set -e

echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files (WhiteNoise)..."
python manage.py collectstatic --noinput

# Idempotent reference-data seeds. Off by default; set RUN_SEED=1 for the first boot
# (or run the seed_* commands manually via `compose exec backend ...`).
case "${RUN_SEED:-0}" in
	1 | true | TRUE | yes)
		echo "[entrypoint] Seeding reference data..."
		python manage.py seed_training
		python manage.py seed_nutrition
		python manage.py seed_protocols
		python manage.py seed_diary
		;;
esac

echo "[entrypoint] Starting gunicorn..."
exec gunicorn config.wsgi:application \
	--bind 0.0.0.0:8000 \
	--workers "${GUNICORN_WORKERS:-3}" \
	--timeout "${GUNICORN_TIMEOUT:-60}" \
	--access-logfile - \
	--error-logfile -
