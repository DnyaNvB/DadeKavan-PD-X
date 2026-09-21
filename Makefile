.PHONY: up down logs migrate superuser worker-a worker-b django api test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	python django_app/manage.py migrate

superuser:
	python django_app/manage.py createsuperuser

worker-a:
	python -m workers.worker_a

worker-b:
	python -m workers.worker_b

django:
	python django_app/manage.py runserver 0.0.0.0:6280

api:
	uvicorn fastapi_app.main:app --host 0.0.0.0 --port 6288

test:
	pytest -q
