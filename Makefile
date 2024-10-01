SHELL := /bin/bash
include .env
export

CURDATE=$(shell date +"%Y%m%d")
CURDATE_TIME=$(shell date +"%Y-%m-%d-%H-%M-%S")
DOCKER_APP_GOOGLE_APPLICATION_PATH=/google_auth_file/key_file.json

#!make
#include config/.envs/mysql.env
#export $(shell sed 's/=.*//' .env)

build:
	docker-compose build --no-cache

run:
	docker-compose up -d

start:
	docker-compose start

restart:
	docker-compose restart

stop:
	docker-compose stop

rebuild: stop build run

rebuildnginx:
	docker-compose down nginx
	docker-compose build --no-cache nginx
	docker-compose up -d nginx

bashflask:
	docker-compose run --rm --entrypoint "" flask /bin/bash

bashcelery:
	docker-compose run --rm --entrypoint "" celery-worker /bin/bash

bashnginx:
	docker-compose run --rm nginx /bin/sh

bashdb:
	docker-compose run --rm db /bin/sh

bashlotus:
	docker-compose run --rm lotus2 /bin/sh

logsflask:
	docker-compose logs -f --tail=200 flask

logscelery:
	docker-compose logs -f --tail=200 celery-worker

logsnginx:
	docker-compose logs -f --tail=200 nginx

logsredis:
	docker-compose logs -f --tail=200 redis

logslotus:
	docker-compose logs -f --tail=200 lotus2

migration:
	docker-compose exec flask alembic revision --autogenerate -m "${description}"

delete_expired_files:
	docker-compose exec flask python delete_expired_files.py

migrate:
	docker-compose exec flask alembic upgrade head

lint:
	docker-compose run flake8

black:
	docker-compose run black
	docker-compose run flake8

runmysql:
	docker-compose run --rm db mysql -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE}

dbimport:
	docker-compose run --rm -T db mysql -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < backup/backup.sql

dbexport:
	docker-compose run --rm db mysqldump -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} > backup/backup.sql
	ls -l backup/backup.sql

dbbackup:
	gsutil cp backup/backup.sql gs://${GOOGLE_STORAGE_BUCKET_NAME}/backup/

sshvm:
	gcloud compute ssh ${GOOGLE_VM_PROPERTY}

ssh:
	ssh ${SSH_KEY} ubuntu@${SERVER_IP}

copyssh:
	gcloud compute scp ~/.ssh/id_rsa.pub ${GOOGLE_VM_PROPERTY}:~/

echo:
	echo $${GOOGLE_APPLICATION_CREDENTIALS_PATH}
