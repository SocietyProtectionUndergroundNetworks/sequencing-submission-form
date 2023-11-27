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

bashnginx:
	docker-compose run --rm nginx /bin/sh

logsflask:
	docker-compose logs flask

echo:
	echo $${GOOGLE_APPLICATION_CREDENTIALS_PATH}
