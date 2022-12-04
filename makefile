#vars
APP=${PANEL_APP}
IMAGENAME=${DOCKER_USERNAME}/${APP}
RUNNAME=${DOCKER_USERNAME}_${APP}
VERSION=latest
IMAGEFULLNAME=${IMAGENAME}:${VERSION}
PROJECTNAME=${DOCKER_USERNAME}_${APP}

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

pull:
	docker pull ${IMAGEFULLNAME}

run: 
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/app/shared_data -v ${HOME}/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=production -e PORT=${PORT} -e GCLOUD_PROJECT=${GCLOUD_PROJECT} -e DOCKER_USERNAME=${DOCKER_USERNAME} ${IMAGEFULLNAME}

run-it:
	docker run --rm --entrypoint "" -e PANEL_ENV=development -it ${IMAGEFULLNAME} /bin/sh

run-development: 
	docker run -d --name ${RUNNAME} -v ${PWD}/shared_data:/app/shared_data -p 127.0.0.1:${PORT}:${PORT} -e PANEL_ENV=development -e PORT=${PORT} -e DOCKER_USERNAME=${DOCKER_USERNAME} ${IMAGEFULLNAME}

stop: 
	docker stop ${RUNNAME}

up:
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --scale web=3; \
	else \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d web nginx --scale web=3; \
	fi;

up-build:
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build --scale web=3
	else \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build web nginx --scale web=3; \
	fi;
down:
	docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . down

up-init:
	bash docker/compose_init.sh

db-clean:
	docker run --rm --name clean_database --entrypoint "" -v ${PWD}/shared_data:/app/shared_data -e PANEL_ENV=production ${IMAGEFULLNAME} /bin/sh -c "data-lunch db clean --yes"

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

ssl-cert:
	mkdir -p ./ssl/conf/live/${DOMAIN}/
	curl https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > ./ssl/conf/options-ssl-nginx.conf
	openssl dhparam -out ./ssl/conf/ssl-dhparams.pem 2048
	openssl req -nodes -x509 -newkey rsa:2048 -keyout ./ssl/conf/live/${DOMAIN}/privkey.pem -out ./ssl/conf/live/${DOMAIN}/fullchain.pem  -subj "/C=IT/ST=Lombardia/L=Milan/O=MIC/OU=IT/CN=${DOMAIN}/"

rm-ssl-cert:
	rm -R ./ssl

all: build

clean:
	docker system prune -f