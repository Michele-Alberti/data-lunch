#vars
APP=${PANEL_APP}
USERNAME=${DOCKER_USERNAME}
IMAGENAME=${USERNAME}/${APP}
RUNNAME=${USERNAME}_${APP}
VERSION=latest
CONTAINERNAME=${IMAGENAME}
IMAGEFULLNAME=${CONTAINERNAME}:${VERSION}
PROJECTNAME=${USERNAME}_${APP}
PORT=${PANEL_PORT}

.PHONY: help build push all clean

help:
	@echo "Makefile commands:"
	@echo "build"
	@echo "push"
	@echo "all"

.DEFAULT_GOAL := all

build:
	docker build -t ${IMAGEFULLNAME} -f docker/web/Dockerfile.web .

push:
	docker push ${IMAGEFULLNAME}

run: 
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/app/shared_data -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=production -e PANEL_PORT=${PORT} ${IMAGEFULLNAME}

run-it:
	docker run -it ${IMAGEFULLNAME} /entry.sh /bin/sh

run-development: 
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/app/shared_data -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=development -e _PANEL_PORT=${PORT} ${IMAGEFULLNAME}

stop: 
	docker stop ${RUNNAME}

up:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --scale web=3

up-build:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build --scale web=3

down:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . down

all: build

clean:
	docker system prune -f