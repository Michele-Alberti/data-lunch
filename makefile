#vars
APP=${PANEL_APP}
USERNAME=${DOCKER_USERNAME}
IMAGENAME=${USERNAME}/${APP}
RUNNAME=${USERNAME}_${APP}
VERSION=latest
IMAGEFULLNAME=${IMAGENAME}:${VERSION}
PROJECTNAME=${USERNAME}_${APP}

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
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/tmp/shared_data -v ${HOME}/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=production -e PORT=${PORT} -e GCLOUD_PROJECT=${GCLOUD_PROJECT} ${IMAGEFULLNAME}

run-it:
	docker run -it ${IMAGEFULLNAME} /entry.sh /bin/sh

run-development: 
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/app/shared_data -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=development -e PORT=${PORT} ${IMAGEFULLNAME}

stop: 
	docker stop ${RUNNAME}

up:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --scale web=3

up-build:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build --scale web=3

down:
	docker-compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . down

gcp-config:
	gcloud config configurations create ${APP}
	gcloud config set project ${GCLOUD_PROJECT}
	gcloud config set run/region us-east1
	gcloud auth login
	gcloud auth application-default login
	gcloud auth application-default set-quota-project ${GCLOUD_PROJECT}


gcp-revoke:
	gcloud auth application-default revoke

gcp-build: build
	docker tag ${IMAGEFULLNAME} us-east1-docker.pkg.dev/${GCLOUD_PROJECT}/mic-datalunch-p-are-usea1-repo-6vk4/web:${VERSION}
	docker push us-east1-docker.pkg.dev/${GCLOUD_PROJECT}/mic-datalunch-p-are-usea1-repo-6vk4/web:${VERSION}

gcp-deploy:
	gcloud run deploy --image=us-east1-docker.pkg.dev/${GCLOUD_PROJECT}/mic-datalunch-p-are-usea1-repo-6vk4/web:${VERSION} --platform managed --update-env-vars PANEL_ENV=production,PANEL_APP=data-lunch-app

all: build

clean:
	docker system prune -f