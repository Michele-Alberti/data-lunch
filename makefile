# Colors
YELLOW := \033[1;33m
GREEN := \033[1;32m
RED := \033[1;31m
CYAN := \033[1;36m
ORANGE := \033[0;33m
PURPLE := \033[1;35m
WHITE := \033[1;37m
NC := \033[0m

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

# Directories
CERT_DIR := ssl

# Conda commands
CONDA_ACTIVATE_BASE:=source ${CONDA_ROOT}/etc/profile.d/conda.sh; conda activate;

help:
	@echo -e " ${PURPLE}                                  LIST OF AVAILABLE COMMANDS                                    ${NC}"
	@echo -e " ${RED}======================|=========================================================================${NC}"
	@echo -e " ${RED}Command               | Description                                                             ${NC}"
	@echo -e " ${RED}======================|=========================================================================${NC}"
	@echo -e " ${YELLOW}SETUP ------------------------------------------------------------------------------------------${NC}"
	@echo -e " ${WHITE}  help                :${NC} prints this help message"
	@echo -e " ${WHITE}  gcp-config          :${NC} configures and authenticates GCP"
	@echo -e " ${WHITE}  gcp-revoke          :${NC} removes GCP configurations and authentication"
	@echo -e " ${WHITE}  ssl-gen-certificate :${NC} creates SSL certificate"
	@echo -e " ${WHITE}  ssl-rm-certificate  :${NC} removes SSL certificate"
	@echo -e " ${WHITE}  generate-secrets    :${NC} print random cookies and encryption secrets"
	@echo -e " ${YELLOW}DOCKER -----------------------------------------------------------------------------------------${NC}"
	@echo -e " ${WHITE}  docker-build        :${NC} builds docker image from Dockerfile"
	@echo -e " ${WHITE}  docker-push         :${NC} pushes docker image to DockerHub repository"
	@echo -e " ${WHITE}  docker-pull         :${NC} pulls docker image from DockerHub repository"
	@echo -e " ${WHITE}  docker-build-push   :${NC} builds and pushes docker image to DockerHub repository"
	@echo -e " ${WHITE}  docker-run          :${NC} runs docker image"
	@echo -e " ${WHITE}  docker-run-it       :${NC} runs docker image in interactive mode"
	@echo -e " ${WHITE}  docker-stop         :${NC} stops docker image"
	@echo -e " ${WHITE}  docker-db-run       :${NC} runs database image"
	@echo -e " ${WHITE}  docker-db-stop      :${NC} stops database image"
	@echo -e " ${WHITE}  docker-up           :${NC} starts docker compose"
	@echo -e " ${WHITE}  docker-up-build     :${NC} builds and start docker compose"
	@echo -e " ${WHITE}  docker-down         :${NC} stops docker compose"
	@echo -e " ${WHITE}  docker-up-init      :${NC} initializes docker compose"
	@echo -e " ${YELLOW}CLEAN ------------------------------------------------------------------------------------------${NC}"
	@echo -e " ${WHITE}  clean-folders       :${NC} cleans all folders nb checkpoints, pycache & pytest folders"
	@echo -e " ${WHITE}  clean-docker        :${NC} cleans docker containers and images"
	@echo -e " ${WHITE}  clean               :${NC} runs clean-notebooks, clean-docker, clean-folders, clean-k8s"
	@echo -e " ${YELLOW}DOCS -------------------------------------------------------------------------------------------${NC}"
	@echo -e " ${WHITE}  mkdocs-build        :${NC} build docs with mkdocs command"
	@echo -e " ${WHITE}  mkdocs-serve        :${NC} run mkdocs test server"
	@echo -e " ${WHITE}  mike-serve          :${NC} run mike test server"
	@echo -e " ${WHITE}  docs                :${NC} build docs with selected default command"
	@echo -e " ${WHITE}  docs-serve          :${NC} run default test server"
	@echo -e " ${YELLOW}MISC -------------------------------------------------------------------------------------------${NC}"
	@echo -e " ${WHITE}  interrogate         :${NC} runs interrogate to check code quality"
	@echo -e " ${WHITE}  package-build       :${NC} build python package"
	@echo -e " ${WHITE}  package-publish     :${NC} publish python package to PyPI"
	@echo -e " ${WHITE}  package-install     :${NC} install package with pip from PyPI (use only in a test env)"
	@echo -e " ${WHITE}  package-test-publish:${NC} publish python package to TestPyPI"
	@echo -e " ${WHITE}  package-test-install:${NC} install package with pip from TestPyPI (use only in a test env)"
	@echo -e " ${WHITE}  pre-commit-run      :${NC} runs pre-commit hooks"
	@echo -e " ${WHITE}  commitizen-bump     :${NC} runs commitizen for releasing a new version on 'main' branch"
	@echo -e " ${WHITE}  commitizen-push     :${NC} use git to push commits on 'development' and 'main' branches"
	@echo -e "${RED}=======================|=========================================================================${NC}"
	@echo ""

default: help

# Force execution every time
.PHONY: clean ${K8S_MANIFEST_FILES}

# Pre-check -------------------------------------------------------------------
check-version:
ifndef IMAGE_VERSION
	$(error "IMAGE_VERSION is not set, use 'make [COMMAND] IMAGE_VERSION=latest' to build with 'latest' as version")
endif

check-dialect:
ifndef DB_DIALECT
	$(error DB_DIALECT is not set, add DB_DIALECT=postgresql or DB_DIALECT=sqlite after the make command)
endif

# Setup rules -----------------------------------------------------------------
gcp-config:
	@echo -e "${YELLOW}start GCP config and auth${NC}"
	gcloud config configurations create ${APP}
	gcloud config set project ${GCLOUD_PROJECT}
	gcloud auth login
	gcloud auth application-default login
	gcloud auth application-default set-quota-project ${GCLOUD_PROJECT}
	@echo -e "${GREEN}GCP config and auth done${NC}"

gcp-revoke:
	@echo -e "${YELLOW}remove GCP config and auth${NC}"
	gcloud config configurations activate default
	gcloud config configurations delete ${APP}
	gcloud auth application-default revoke
	@echo -e "${GREEN}GCP config and auth removed${NC}"

ssl-gen-certificate: ssl-rm-certificate
	@echo -e "${YELLOW}create test SSL certificate${NC}"
	mkdir -p ./${CERT_DIR}/conf/live/${DOMAIN}/
	curl https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > \
		./ssl/conf/options-ssl-nginx.conf
	find ./ssl/conf/ -name "ssl-dhparams.pem" -type f -mtime +1 -delete 
	if [[ ! -f ./ssl/conf/ssl-dhparams.pem ]] ;	then \
		echo "building dhparam"; \
		openssl dhparam -out ./ssl/conf/ssl-dhparams.pem 2048; \
	else \
		echo "dhparam already exists" ;\
	fi;
	openssl req -nodes -x509 \
		-newkey rsa:2048 \
		-keyout ./ssl/conf/live/${DOMAIN}/privkey.pem \
		-out ./ssl/conf/live/${DOMAIN}/fullchain.pem \
		-subj "/C=IT/ST=Lombardia/L=Milan/O=MIC/OU=IT/CN=${DOMAIN}/"
	@echo -e "${GREEN}certificate created${NC}"

ssl-rm-certificate:
	@echo -e "${YELLOW}remove test SSL certificate${NC}"
	@-rm -R ssl
	@echo -e "${GREEN}certificate folder removed${NC}"

generate-secrets:
	@echo -e "${YELLOW}print secrets${NC}"	
	@echo "\nCOOKIE SECRET:"
	@panel secret
	@echo "\nENCRIPTION KEY:"
	@panel oauth-secret
	@echo -e "\n${GREEN}done${NC}"

# Docker rules ----------------------------------------------------------------

docker-build: check-version
	@echo -e "${YELLOW}build dl_optima docker image from ./docker/Dockerfile${NC}"
	docker build -t ${IMAGEFULLNAME} -f docker/web/Dockerfile.web .
	docker system prune -f
	@echo -e "${GREEN}build done${NC}"

docker-push: check-version
	@echo -e "${YELLOW}push image to ECR (with version '${IMAGE_VERSION}')${NC}"
	docker push ${IMAGEFULLNAME}
	@echo -e "${GREEN}push done${NC}"

docker-pull: check-version
	@echo -e "${YELLOW}pull image from ECR (selected version: '${IMAGE_VERSION}')${NC}"
	docker pull ${IMAGEFULLNAME}
	@echo -e "${GREEN}pull done${NC}"

docker-build-push: docker-build docker-push

docker-run: check-version
	@echo -e "${YELLOW}run container locally (selected version: '${IMAGE_VERSION}')${NC}"
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
		-e DATA_LUNCH_OAUTH_REDIRECT_URI=${DATA_LUNCH_OAUTH_REDIRECT_URI} \
		-e DATA_LUNCH_DB_PASSWORD=${DATA_LUNCH_DB_PASSWORD} \
		${IMAGEFULLNAME} ${PANEL_ARGS}
	@echo -e "${GREEN}done${NC}"

docker-run-it: check-version
	@echo -e "${YELLOW}run interactive session locally (selected version: '${IMAGE_VERSION}')${NC}"
	docker run --rm --entrypoint "" -e PANEL_ENV=development -it ${IMAGEFULLNAME} /bin/sh
	@echo -e "${GREEN}done${NC}"

docker-stop:
	@echo -e "${YELLOW}stop running container${NC}"
	docker stop ${RUNNAME}
	@echo -e "${GREEN}done${NC}"

docker-db-run:
	@echo -e "${YELLOW}run database locally${NC}"
	docker run -d --name ${DBCONTAINERNAME} \
		-v ${PWD}/shared_data/db_pg:/var/lib/postgresql/data \
		-p 127.0.0.1:${DBPORT}:${DBPORT} \
		-e POSTGRES_USER=data_lunch_rw \
		-e POSTGRES_PASSWORD=${DATA_LUNCH_DB_PASSWORD} \
		-e POSTGRES_DB=data_lunch_database \
		${DBIMAGEFULLNAME}
	@echo -e "${GREEN}done${NC}"

docker-db-stop:
	@echo -e "${YELLOW}stop running database${NC}"
	docker stop ${DBCONTAINERNAME}
	@echo -e "${GREEN}done${NC}"

docker-up: check-dialect
	@echo -e "${YELLOW}start docker compose system${NC}"
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} \
			-f docker/docker-compose.yaml \
			--project-directory . \
			up -d --scale web=3; \
	else \
		if [[ ${DB_DIALECT} == "postgresql" ]] ; then \
			docker compose -p ${PROJECTNAME} \
				-f docker/docker-compose.yaml \
				--project-directory . \
				up -d ${UP_SERVICES} ${DBSERVICE} --scale web=3; \
		else \
			docker compose -p ${PROJECTNAME} \
				-f docker/docker-compose.yaml \
				--project-directory . \
				up -d ${UP_SERVICES} --scale web=3; \
		fi; \
	fi;
	@echo -e "${GREEN}done${NC}"

docker-up-build: check-dialect docker-build
	@echo -e "${YELLOW}start docker compose system${NC}"
	if [[ ${PANEL_ENV} == "production" ]] ; then \
		docker compose -p ${PROJECTNAME} \
			-f docker/docker-compose.yaml \
			--project-directory . \
			up -d --build --scale web=3; \
	else \
		if [[ ${DB_DIALECT} == "postgresql" ]] ; then \
			docker compose -p ${PROJECTNAME} \
				-f docker/docker-compose.yaml \
				--project-directory . \
				up -d --build ${UP_SERVICES} ${DBSERVICE} --scale web=3; \
		else \
			docker compose -p ${PROJECTNAME} \
				-f docker/docker-compose.yaml \
				--project-directory . \
				up -d --build ${UP_SERVICES} --scale web=3; \
		fi; \
	fi;
	@echo -e "${GREEN}done${NC}"

docker-down:
	@echo -e "${YELLOW}stop docker compose system${NC}"
	docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . down
	@echo -e "${GREEN}done${NC}"

docker-up-init:
	@echo -e "${YELLOW}init docker compose system${NC}"
	bash docker/compose_init.sh
	@echo -e "${GREEN}done${NC}"

docker-db-clean:
	@echo -e "${YELLOW}clean database${NC}"
	docker run --rm --name clean_database --entrypoint "" -v ${PWD}/shared_data:/app/shared_data -e PANEL_ENV=production ${IMAGEFULLNAME} /bin/sh -c "data-lunch -o ${PANEL_ARGS} db clean --yes"
	@echo -e "${GREEN}done${NC}"

# Clean rules -----------------------------------------------------------------
clean-folders:
	@echo -e "${YELLOW}clean folders${NC}"
	rm -rf .ipynb_checkpoints __pycache__ .pytest_cache */.ipynb_checkpoints */__pycache__ */.pytest_cache dist site
	@echo -e "${GREEN}done${NC}"

clean-docker:
	@echo -e "${YELLOW}clean docker${NC}"
	docker system prune -f
	@echo -e "${GREEN}done${NC}"

clean: clean-docker clean-folders

# Docs rules ------------------------------------------------------------------
mkdocs-build:
	@echo -e "${YELLOW}build html docs pages${NC}"
	mkdocs build
	@echo -e "${GREEN}done${NC}"

mkdocs-serve:
	@echo -e "${YELLOW}serving without docs version ${NC}"
	@echo -e "${YELLOW}use: ${NC}"
	@echo -e "${CYAN}make mike-serve${NC}"
	@echo -e "${YELLOW}to show existing docs and its versions${NC}"
	@mkdocs serve

mike-serve:
	@mike serve

docs: mkdocs-build
	@echo -e "${GREEN}docs build successfully${NC}"

docs-serve: mkdocs-serve

# Other rules -----------------------------------------------------------------

interrogate:
	@echo -e "${YELLOW}check docstrings${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd;\
	interrogate -vv \
		--ignore-module \
		--ignore-init-method \
		--ignore-private \
		--ignore-magic \
		--ignore-property-decorators \
		--fail-under=80 \
		dlunch
	@echo -e "${GREEN}done${NC}"

package-build:
	@echo -e "${YELLOW}build python package${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd;\
	python -m build
	@echo -e "${GREEN}done${NC}"

package-publish:
	@echo -e "${YELLOW}publish python package to PyPI${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd;\
	twine upload --repository dlunch dist/*
	@echo -e "${GREEN}done${NC}"

package-install:
	@echo -e "${YELLOW}install package from PyPI${NC}"
	pip install dlunch
	@echo -e "${GREEN}done${NC}"

package-test-publish:
	@echo -e "${YELLOW}publish python package to TestPyPI${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd;\
	twine upload --repository testpypi dist/*
	@echo -e "${GREEN}done${NC}"

package-test-install:
	@echo -e "${YELLOW}install package from TestPyPI${NC}"
	pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple dlunch
	@echo -e "${GREEN}done${NC}"

pre-commit-run:
	@echo -e "${YELLOW}run pre-commit hooks${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd;\
	pre-commit run
	@echo -e "${GREEN}done${NC}"

commitizen-bump:
	@echo -e "${YELLOW}run commitizen bump${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd && \
	git checkout development && \
	git pull --ff-only && \
	git checkout main && \
	git pull --ff-only && \
	git merge development --no-ff && \
	cz bump --no-verify && \
	git checkout development && \
	git merge main --no-ff
	@echo -e "${GREEN}done${NC}"

commitizen-push:
	@echo -e "${YELLOW}run commitizen push${NC}"
	@${CONDA_ACTIVATE_BASE} \
	conda activate ci-cd && \
	git checkout development && \
	git pull --ff-only && \
	git checkout main && \
	git pull --ff-only && \
	git push &&\
	git push --tags &&\
	git checkout development && \
	git push
	@echo -e "${GREEN}done${NC}"

send-ip-email:
	@echo -e "${YELLOW}send email with GCP instance IP${NC}"
	docker run --rm --name send_email \
		--entrypoint "" \
		-v ${PWD}/scripts:/app/scripts \
		-v ${PWD}/shared_data:/app/shared_data \
		-e MAIL_USER=${MAIL_USER} \
		-e MAIL_APP_PASSWORD=${MAIL_APP_PASSWORD} \
		-e MAIL_RECIPIENTS=${MAIL_RECIPIENTS} \
		-e DOMAIN=${DOMAIN} \
		${IMAGEFULLNAME} /bin/sh -c "python /app/scripts/send_email_with_ip.py ${PANEL_ARGS}"
	@echo -e "${GREEN}done${NC}"

create-users-credentials:
	@echo -e "${YELLOW}create user credentials from list in GCP storage${NC}"
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
	@echo -e "${GREEN}done${NC}"
