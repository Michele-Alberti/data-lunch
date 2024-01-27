# Data Lunch <!-- omit in toc -->

The ultimate web app for a well organized lunch.

## 1. Table of contents

- [1. Table of contents](#1-table-of-contents)
- [2. Development environment setup](#2-development-environment-setup)
  - [2.1. Miniconda](#21-miniconda)
  - [2.2. Environment variables](#22-environment-variables)
    - [2.2.1. General](#221-general)
    - [2.2.2. Docker and Google Cloud Platform](#222-docker-and-google-cloud-platform)
    - [2.2.3. TLS/SSL Certificate](#223-tlsssl-certificate)
    - [2.2.4. Encryption and Authorization](#224-encryption-and-authorization)
  - [2.3. Setup the development environment](#23-setup-the-development-environment)
  - [2.4. Manually install data-lunch CLI](#24-manually-install-data-lunch-cli)
  - [2.5. Running the docker-compose system](#25-running-the-docker-compose-system)
  - [2.6. Running a single container](#26-running-a-single-container)
- [3. Additional installations before contributing](#3-additional-installations-before-contributing)
  - [3.1. Pre-commit hooks](#31-pre-commit-hooks)
  - [3.2. Commitizen](#32-commitizen)
- [4. Release strategy from `development` to `main` branch](#4-release-strategy-from-development-to-main-branch)
- [5. Google Cloud Platform utilities](#5-google-cloud-platform-utilities)

## 2. Development environment setup

The following steps will guide you through the installation procedure.

### 2.1. Miniconda

[<img style="position: relative; bottom: 3px;" src="https://docs.conda.io/en/latest/_images/conda_logo.svg" alt="Conda" width="80"/>](https://docs.conda.io/en/latest/) is required for creating the development environment (it is suggested to install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)).

Use the terminal for navigating to the repository base directory.\
Use the following command in your terminal to create an environment named `data-lunch` manually.  
Otherwise use the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) to activate the guided installing procedure.

```
conda env create -f environment.yml
```

Activate the new _Conda_ environment with the following command.

```
conda activate data-lunch
```
### 2.2. Environment variables

The following environment variables are required for running the _web app_, the _makefile_ or _utility scripts_.

#### 2.2.1. General
| Variable | Type | Description |
|----------|:------:|-------|
`PANEL_APP` | _str_ | app name, _data-lunch-app_ by default (used by `makefile`)
`PANEL_ENV` | _str_ | environment, e.g. _development_, _quality_, _production_
`PANEL_ARGS` | _str_ | additional arguments passed to _Hydra_ (e.g. `panel/gui=major_release`)
`PORT` | _int_ | port used bu the web app (or the container), default to _5000_

#### 2.2.2. Docker and Google Cloud Platform
| Variable | Type | Description |
|----------|:------:|-------|
`DOCKER_USERNAME` | _str_ | your _Docker Hub_ username, used by `makefile` and stats panel to extract container name (optional)
`IMAGE_VERSION` | _str_ |  _Docker_ image version, typically `stable` or `latest`
`GCLOUD_PROJECT` | _str_ | _Google Cloud Platform_ `project_id`, used by `makefile` for _GCP's CLI_ authentication and for uploading the database to _gcp_ storage, if active in web app configuration files (see panel.scheduled_tasks)
`GCLOUD_BUCKET` | _str_ | _Google Cloud Platform_ `bucket`, used for uploading database to _gcp_ storage, if active in web app configuration files (see panel.scheduled_tasks)
`MAIL_USER` | _str_ | email client user, used for sending emails containing the instance IP, e.g._mywebappemail@email.com_ (used only for _Google Cloud Platform_)
`MAIL_APP_PASSWORD` | _str_ | email client password used for sending emails containing the instance IP (used only for _Google Cloud Platform_)
`MAIL_RECIPIENTS` | _str_ | email recipients as string, separated by `,` (used for sending emails containing the instance IP when hosted on _Google Cloud Platform_)
`DUCKDNS_URL` | _str_ | _URL_ used in `compose_init.sh` to update dynamic address (see _Duck DNS's_ instructions for details, used when hosted on _Google Cloud Platform_)

#### 2.2.3. TLS/SSL Certificate
| Variable | Type | Description |
|----------|:------:|-------|
`CERT_EMAIL` | _str_ | email for registering _SSL certificates_, shared with the authority _Let's Encrypt_ (via `certbot`)
`DOMAIN` | _str_ |  domain name, e.g. _mywebapp.com_

#### 2.2.4. Encryption and Authorization
| Variable | Type | Description |
|----------|:------:|-------|
`DATA_LUNCH_COOKIE_SECRET` | _str_ | _Secret_ used for securing the authentication cookie (use `make generate-secrets` to generate a valid secret)
`DATA_LUNCH_OAUTH_ENC_KEY` | _str_ | _Encription key_ used by the OAuth algorithm for encryption (use `make generate-secrets` to generate a valid secret)
`DATA_LUNCH_OAUTH_KEY` | _str_ | _OAuth key_ used for configuring the OAuth provider (_GitHub_, _Azure_)
`DATA_LUNCH_OAUTH_SECRET` | _str_ | _OAuth secret_ used for configuring the OAuth provider (_GitHub_, _Azure_)
`DATA_LUNCH_OAUTH_REDIRECT_URI` | _str_ | _OAuth redirect uri_ used for configuring the OAuth provider (_GitHub_, _Azure_), do not set to use default value
`DATA_LUNCH_OAUTH_TENANT_ID` | _str_ | _OAuth tenant id_ used for configuring the OAuth provider (_Azure_), do not set to use default value
`DATA_LUNCH_DB_USER` | _str_ | _Postgresql_ user, do not set to use default value
`DATA_LUNCH_DB_PASSWORD` | _str_ | _Postgresql_ password
`DATA_LUNCH_DB_HOST` | _str_ | _Postgresql_ host, do not set to use default value
`DATA_LUNCH_DB_PORT` | _str_ | _Postgresql_ port, do not set to use default value
`DATA_LUNCH_DB_DATABASE` | _str_ | _Postgresql_ database, do not set to use default value
`DATA_LUNCH_DB_SCHEMA` | _str_ | _Postgresql_ schema, do not set to use default value

### 2.3. Setup the development environment

Use the setup script (`setup_dev_env.sh`) to install all the required development tools.

Use `source` to properly launch the script.

```
source setup_dev_env.sh
```

### 2.4. Manually install data-lunch CLI

> This step is not required if the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) is used.

The CLI is distributed with setuptools instead of using Unix shebangs.  
It is a very simple utility to initialize and delete the app database. There are different use cases:

- Create/delete the _sqlite_ database used by the app
- Initialize/drop tables inside the _sqlite_ database

Use the following command for generating the CLI executable from the `setup.py` file, it will install your package locally.

```
pip install .
```

If you want to make some changes to the source code it is suggested to use the following option.

```
pip install --editable .
```

It will just link the package to the original location, basically meaning any changes to the original package would reflect directly in your environment.

Now you can activate the _Conda_ environment and access the _CLI_ commands directly from the terminal (without using annoying _shebangs_ or prepending `python` to run your _CLI_ calls).

Test that everything is working correctly with the following commands.

```
data-lunch --version
data-lunch --help
```

### 2.5. Running the docker-compose system

Since this app will be deployed with an hosting service a _Dockerfile_ to build a container image is available.  
The docker compose file (see `docker-compose.yaml`) builds the web app container along with a _load balancer_ (the _nginx_ container)
to improve the system scalability.

Look inside the `makefile` to see the `docker` and `docker-compose` options.

To build and run the dockerized system you have to install [Docker](https://docs.docker.com/get-docker/).  
Call the following `make` command to start the build process.

```
make up-init up-build
```

`up-init` initialize the _ssl certificate_ based on the selected environment (as set in the environment variable `PANEL_ENV`, i.e. _development_ or _production_).  
Call only `make` (without arguments) to trigger the same command.  
Not initializing _ssl certificate folders_ will result in an `nginx` container failure on start-up.

The two images are built and the two containers are started.  

You can then access your web app at `http://localhost:4000`.

> **Note:**  
> You can also use `make up` to spin up the containers if you do not need to re-build any image or initialize ssl certificate folders.

### 2.6. Running a single container

It is possible to launch a single server by calling the following command.

```
make build

make run
```

You can then access your web app at `http://localhost:5000` (if the deafult `PORT` is selected).

## 3. Additional installations before contributing

> This step is not required if the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) is used.

Before contributing please create the `pre-commit` and `commitizen` environments.

```
cd requirements
conda env create -f pre-commit.yml
conda env create -f commitizen.yml
```

### 3.1. Pre-commit hooks

> This step is not required if the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) is used.

Then install the precommit hooks.

```
conda activate pre-commit
pre-commit install
pre-commit autoupdate
```

Optionally run hooks on all files.

```
pre-commit run --all-files
```

### 3.2. Commitizen

> This step is not required if the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) is used.

The _Commitizen_ hook checks that rules for _conventional commits_ are respected in commits messages.
Use the following command to enjoy _Commitizen's_ interactive prompt.

```
conda activate commitizen
cz commit
```

`cz c` is a shorther alias for `cz commit`.

## 4. Release strategy from `development` to `main` branch

> This step is required only if the CI-CD pipeline on _GitHub_ does not work.

In order to take advantage of _Commitizen_ `bump` command follow this guideline.

First check that you are on the correct branch.

```
git checkout main
```

Then start the merge process forcing it to stop before commit (`--no-commit`) and without using the _fast forward_ strategy (`--no-ff`).

```
git merge development --no-commit --no-ff
```

Check that results match your expectations then commit (you can leave the default message).

```
git commit
```

Now _Commitizen_ `bump` command will add an additional commit with updated versions to every file listed inside `pyproject.toml`.

```
cz bump --no-verify
```

You can now merge results of the release process back to the `development` branch.

```
git checkout development
git merge main --no-ff
```

Use _"update files from last release"_ or the default text as commit message.

## 5. Google Cloud Platform utilities

> This step is not required if the [setup script](#23-setup-the-development-environment-by-using-the-setup-script) is used.

The makefile has two rules for conviniently setting up and removing authentication credentials for _Google Cloud Platform_ command line interface: `gcp-config` and `gcp-revoke`.