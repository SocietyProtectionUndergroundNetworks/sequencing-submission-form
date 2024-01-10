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

bashflask:
	docker-compose run --rm --entrypoint "" flask /bin/bash

bashcelery:
	docker-compose run --rm --entrypoint "" celery-worker /bin/bash

bashnginx:
	docker-compose run --rm nginx /bin/sh

bashdb:
	docker-compose run --rm db /bin/sh

logsflask:
	docker-compose logs -f --tail=200 flask

logscelery:
	docker-compose logs -f --tail=200 celery-worker

migration:
	docker-compose exec flask alembic revision --autogenerate -m "${description}"

migrate:
	docker-compose exec flask alembic upgrade head
	
mysql:
	docker-compose run --rm db mysql -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE}	

dbimport:
	docker-compose run --rm -T db mysql -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < backup/backup.sql

dbexport:
	docker-compose run --rm db mysqldump -h${MYSQL_HOST} -u${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} > backup/backup.sql
	ls -l backup/backup.sql


echo:
	echo $${GOOGLE_APPLICATION_CREDENTIALS_PATH}
