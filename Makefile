SHELL := /bin/bash
include .env
export

CURDATE=$(shell date +"%Y%m%d")
CURDATE_TIME=$(shell date +"%Y-%m-%d-%H-%M-%S")
DOCKER_IMAGE_NAME=spun-dna-data-upload-form
DOCKER_APP_NAME=spun-data-upload-app
DOCKER_APP_GOOGLE_APPLICATION_PATH=/google_auth_file/key_file.json

#!make
#include config/.envs/mysql.env
#export $(shell sed 's/=.*//' .env)

build:
	docker build --tag ${DOCKER_IMAGE_NAME} .

run:
	docker run -d \
		-p 56733:8080 \
		--name=${DOCKER_APP_NAME} \
		-v .:/app \
		-v ${GOOGLE_APPLICATION_CREDENTIALS_PATH}:${DOCKER_APP_GOOGLE_APPLICATION_PATH} \
		-e "GOOGLE_APPLICATION_CREDENTIALS=${DOCKER_APP_GOOGLE_APPLICATION_PATH}" \
		--env-file=.env \
		${DOCKER_IMAGE_NAME}
start: run

restart: stop remove run

stop:
	docker stop ${DOCKER_APP_NAME}

remove:
	docker remove ${DOCKER_APP_NAME}
	
rebuild: stop remove build run
	
bash:
	docker exec -it ${DOCKER_APP_NAME} /bin/sh

logs: 
	docker logs ${DOCKER_APP_NAME}

echo:
	echo $${GOOGLE_APPLICATION_CREDENTIALS_PATH}
