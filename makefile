# Data-Lunch variables
APP=${PANEL_APP}
IMAGENAME=${DOCKER_USERNAME}/${APP}
RUNNAME=${DOCKER_USERNAME}_${APP}
VERSION=${IMAGE_VERSION}
IMAGEFULLNAME=${IMAGENAME}:${VERSION}
PROJECTNAME=${DOCKER_USERNAME}_${APP}
# Database variables (used if not sqlite)
DBNAME:=postgres
DBSERVICE:=db
DBCONTAINERNAME:=${DBNAME}_${DBSERVICE}
DBIMAGEFULLNAME:=${DBNAME}:${VERSION}
DBPORT:=5432
# Docker compose up
UP_SERVICES:=web nginx

.PHONY: help build push all clean

help:
	@echo "Makefile commands:"
	@echo "build"
	@echo "push"
	@echo "all"

.DEFAULT_GOAL := help

check-dialect:
ifndef DB_DIALECT
	$(error DB_DIALECT is not set, add DB_DIALECT=postgresql or DB_DIALECT=sqlite after the make command)
endif

build:
	docker build -t ${IMAGEFULLNAME} -f docker/web/Dockerfile.web .

push:
	docker push ${IMAGEFULLNAME}

pull:
	docker pull ${IMAGEFULLNAME}

run: 
	docker run -d --name ${RUNNAME} \
		-v ${PWD}/shared_data:/app/shared_data \
		-p 127.0.0.1:${PORT}:${PORT} \
		-e PANEL_ENV=production \
		-e PORT=${PORT} \
		-e GCLOUD_PROJECT=${GCLOUD_PROJECT} \
		-e GCLOUD_BUCKET=${GCLOUD_BUCKET} \
		-e DOCKER_USERNAME=${DOCKER_USERNAME} \
		-e DATA_LUNCH_COOKIE_SECRET=${DATA_LUNCH_COOKIE_SECRET} \
		-e DATA_LUNCH_OAUTH_ENC_KEY=${DATA_LUNCH_OAUTH_ENC_KEY} \
		-e DATA_LUNCH_OAUTH_KEY=${DATA_LUNCH_OAUTH_KEY} \
		-e DATA_LUNCH_OAUTH_SECRET=${DATA_LUNCH_OAUTH_SECRET} \
		-e DATA_LUNCH_OAUTH_SECRET=${DATA_LUNCH_OAUTH_REDIRECT_URI} \
		${IMAGEFULLNAME} ${PANEL_ARGS}

run-it:
	docker run --rm --entrypoint "" -e PANEL_ENV=development -it ${IMAGEFULLNAME} /bin/sh

run-development: 
	docker run -d --name ${RUNNAME} \
	-v ${PWD}/shared_data:/app/shared_data \
	-p 127.0.0.1:${PORT}:${PORT} \
	-e PANEL_ENV=development \
	-e PORT=${PORT} \
	-e GCLOUD_PROJECT=${GCLOUD_PROJECT} \
	-e GCLOUD_BUCKET=${GCLOUD_BUCKET} \
	-e DOCKER_USERNAME=${DOCKER_USERNAME} \
	-e DATA_LUNCH_COOKIE_SECRET=${DATA_LUNCH_COOKIE_SECRET} \
	-e DATA_LUNCH_OAUTH_ENC_KEY=${DATA_LUNCH_OAUTH_ENC_KEY} \
	-e DATA_LUNCH_OAUTH_KEY=${DATA_LUNCH_OAUTH_KEY} \
	-e DATA_LUNCH_OAUTH_SECRET=${DATA_LUNCH_OAUTH_SECRET} \
	-e DATA_LUNCH_OAUTH_SECRET=${DATA_LUNCH_OAUTH_REDIRECT_URI} \
	${IMAGEFULLNAME} ${PANEL_ARGS}


stop: 
	docker stop ${RUNNAME}

run-db: 
	docker run -d --name ${DBCONTAINERNAME} \
	-v ${PWD}/shared_data/db_pg:/var/lib/postgresql/data \
	-p 127.0.0.1:${DBPORT}:${DBPORT} \
	-e POSTGRES_USER=data_lunch_rw \
	-e POSTGRES_PASSWORD=${DATA_LUNCH_DB_PASSWORD} \
	-e POSTGRES_DB=data_lunch_database \
	${DBIMAGEFULLNAME}

stop-db: 
	docker stop ${DBCONTAINERNAME}

send-ip-email:
	docker run --rm --name send_email \
	--entrypoint "" \
	-v ${PWD}/scripts:/app/scripts \
	-v ${PWD}/shared_data:/app/shared_data \
	-e MAIL_USER=${MAIL_USER} \
	-e MAIL_APP_PASSWORD=${MAIL_APP_PASSWORD} \
	-e MAIL_RECIPIENTS=${MAIL_RECIPIENTS} \
	-e DOMAIN=${DOMAIN} \
	${IMAGEFULLNAME} /bin/sh -c "python /app/scripts/send_email_with_ip.py ${PANEL_ARGS}"

create-users-credentials:
	docker run --rm --name create_users \
	--entrypoint "" \
	-v ${PWD}/scripts:/app/scripts \
	-v ${PWD}/shared_data:/app/shared_data \
	-e PANEL_ENV=${PANEL_ENV} \
	-e GCLOUD_BUCKET=${GCLOUD_BUCKET} \
	-e GCLOUD_PROJECT=${GCLOUD_PROJECT} \
	-e MAIL_USER=${MAIL_USER} \
	-e MAIL_APP_PASSWORD=${MAIL_APP_PASSWORD} \
	-e MAIL_RECIPIENTS=${MAIL_RECIPIENTS} \
	-e DOMAIN=${DOMAIN} \
	${IMAGEFULLNAME} /bin/sh -c "python /app/scripts/create_users_from_list.py ${PANEL_ARGS}"

up: check-dialect
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --scale web=3; \
	else \
		if [[ ${DB_DIALECT} == "postgresql" ]] ; then \
			docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d ${UP_SERVICES} ${DBSERVICE} --scale web=3; \
		else \
			docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d ${UP_SERVICES} --scale web=3; \
		fi; \
	fi;

up-build: check-dialect build
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build --scale web=3; \
	else \
		if [[ ${DB_DIALECT} == "postgresql" ]] ; then \
			docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build ${UP_SERVICES} ${DBSERVICE} --scale web=3; \
		else \
			docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up -d --build ${UP_SERVICES} --scale web=3; \
		fi; \
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
	gcloud auth login
	gcloud auth application-default login
	gcloud auth application-default set-quota-project ${GCLOUD_PROJECT}

gcp-revoke:
	gcloud config configurations activate default
	gcloud config configurations delete ${APP}
	gcloud auth application-default revoke

ssl-cert:
	mkdir -p ./ssl/conf/live/${DOMAIN}/
	curl https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > ./ssl/conf/options-ssl-nginx.conf
	find ./ssl/conf/ -name "ssl-dhparams.pem" -type f -mtime +1 -delete 
	if [[ ! -f ./ssl/conf/ssl-dhparams.pem ]] ;	then \
		echo "building dhparam"; \
		openssl dhparam -out ./ssl/conf/ssl-dhparams.pem 2048; \
	else \
		echo "dhparam already exists" ;\
	fi;
	openssl req -nodes -x509 -newkey rsa:2048 -keyout ./ssl/conf/live/${DOMAIN}/privkey.pem -out ./ssl/conf/live/${DOMAIN}/fullchain.pem  -subj "/C=IT/ST=Lombardia/L=Milan/O=MIC/OU=IT/CN=${DOMAIN}/"

rm-ssl-cert:
	rm -R ./ssl

generate-secrets:
	@echo "\n*** START ***"
	@echo "\nCOOKIE SECRET:"
	@panel secret
	@echo "\nENCRIPTION KEY:"
	@panel oauth-secret
	@echo "\n***  END  ***\n"

all: up-init up-build

clean:
	docker system prune -f