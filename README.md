# Data Lunch <!-- omit in toc -->

The ultimate web app for a well organized lunch.

## 1. Table of contents

- [1. Table of contents](#1-table-of-contents)
- [2. Development environment setup](#2-development-environment-setup)
  - [2.1. Miniconda](#21-miniconda)
  - [2.2. Setup the development environment](#22-setup-the-development-environment)
  - [2.3. Environment variables](#23-environment-variables)
    - [2.3.1. General](#231-general)
    - [2.3.2. Docker and Google Cloud Platform](#232-docker-and-google-cloud-platform)
    - [2.3.3. TLS/SSL Certificate](#233-tlsssl-certificate)
    - [2.3.4. Encryption and Authorization](#234-encryption-and-authorization)
  - [2.4. Manually install the development environment](#24-manually-install-the-development-environment)
  - [2.5. Manually install data-lunch CLI](#25-manually-install-data-lunch-cli)
  - [2.6. Running the docker-compose system](#26-running-the-docker-compose-system)
  - [2.7. Running a single container](#27-running-a-single-container)
  - [2.8. Running locally](#28-running-locally)
- [3. Additional installations before contributing](#3-additional-installations-before-contributing)
  - [3.1. Pre-commit hooks](#31-pre-commit-hooks)
  - [3.2. Commitizen](#32-commitizen)
- [4. Release strategy from `development` to `main` branch](#4-release-strategy-from-development-to-main-branch)
- [5. Google Cloud Platform utilities](#5-google-cloud-platform-utilities)

## 2. Development environment setup

The following steps will guide you through the installation procedure.

### 2.1. Miniconda

[Conda](https://docs.conda.io/en/latest/) is required for creating the development environment (it is suggested to install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)).

### 2.2. Setup the development environment

Use the setup script (`setup_dev_env.sh`) to install all the required development tools.

Use `source` to properly launch the script.

```
source setup_dev_env.sh
```

> [!IMPORTANT]
> The setup script will take care of setting up the development environment for you.
> The script installs:
> - 3 environments (`data-lunch` for development, `ci-cd` for _pre-commit_ and other utilities, `gc-sdk` for interacting with _Google Cloud Platform_)
> - _pre-commit_ hooks
> - `data-lunch` command line

### 2.3. Environment variables

The following environment variables are required for running the _web app_, the _makefile_ or _utility scripts_.

#### 2.3.1. General
| Variable | Type | Required | Description |
|----------|:----:|:--------:|-------------|
`PANEL_APP` | _str_ | ✔️ | app name, _data-lunch-app_ by default (used by `makefile`)
`PANEL_ENV` | _str_ | ✔️ | environment, e.g. _development_, _quality_, _production_, affects app configuration (_Hydra_) and build processes (_makefile_)
`PANEL_ARGS` | _str_ | ❌ | additional arguments passed to _Hydra_ (e.g. `panel/gui=major_release`) in _makefile_ and `docker-compose` commands
`PORT` | _int_ | ✔️ | port used by the web app (or the container), default to _5000_; affects app configuration and build process (it is used by _makefile_, _Hydra_ and _Docker_)

#### 2.3.2. Docker and Google Cloud Platform
> [!NOTE]
> The following variables are mainly used during the building process or by external scripts.

| Variable | Type | Required | Description |
|----------|:----:|:--------:|-------------|
`DOCKER_USERNAME` | _str_ | ❌ | your _Docker Hub_ username, used by `makefile` and stats panel to extract container name
`IMAGE_VERSION` | _str_ | ❌ | _Docker_ image version, typically `stable` or `latest` (used by _makefile_ and `docker-compose` commands)
`GCLOUD_PROJECT` | _str_ | ❌ | _Google Cloud Platform_ `project_id`, used by `makefile` for _GCP's CLI_ authentication and for uploading the database to _gcp_ storage, if active in web app configuration files (see panel.scheduled_tasks)
`GCLOUD_BUCKET` | _str_ | ❌ | _Google Cloud Platform_ `bucket`, used for uploading database to _gcp_ storage, if active in web app configuration files (see panel.scheduled_tasks)
`MAIL_USER` | _str_ | ❌ | email client user, used for sending emails containing the instance IP, e.g._mywebappemail@email.com_ (used only for _Google Cloud Platform_)
`MAIL_APP_PASSWORD` | _str_ | ❌ | email client password used for sending emails containing the instance IP (used only for _Google Cloud Platform_)
`MAIL_RECIPIENTS` | _str_ | ❌ | email recipients as string, separated by `,` (used for sending emails containing the instance IP when hosted on _Google Cloud Platform_)
`DUCKDNS_URL` | _str_ | ❌ | _URL_ used in `compose_init.sh` to update dynamic address (see _Duck DNS's_ instructions for details, used when hosted on _Google Cloud Platform_)

#### 2.3.3. TLS/SSL Certificate
> [!TIP]
> Use the command `make ssl-gen-certificate` to generate local SSL certificates.

| Variable | Type | Required | Description |
|----------|:----:|:--------:|-------------|
`CERT_EMAIL` | _str_ | ❌ | email for registering _SSL certificates_, shared with the authority _Let's Encrypt_ (via `certbot`); used by `docker-compose` commands
`DOMAIN` | _str_ | ❌ | domain name, e.g. _mywebapp.com_, used by `docker-compose` commands (`certbot`), in email generation (`scripts` folder) and to auto-generate SSL certificates

#### 2.3.4. Encryption and Authorization
> [!NOTE]
> All variables used by _Postgresql_ are not required if `db=sqlite` (default value).  
> All variables used by _OAuth_ are not required if `server=no_auth` (default value).

> [!IMPORTANT]
> `DATA_LUNCH_COOKIE_SECRET` and `DATA_LUNCH_OAUTH_ENC_KEY` are required even if `server=no_auth` is set.

| Variable | Type | Required | Description |
|----------|:----:|:--------:|-------------|
`DATA_LUNCH_COOKIE_SECRET` | _str_ | ✔️ | _Secret_ used for securing the authentication cookie (use `make generate-secrets` to generate a valid secret)
`DATA_LUNCH_OAUTH_ENC_KEY` | _str_ | ✔️ | _Encription key_ used by the OAuth algorithm for encryption (use `make generate-secrets` to generate a valid secret)
`DATA_LUNCH_OAUTH_KEY` | _str_ | ❌ | _OAuth key_ used for configuring the OAuth provider (_GitHub_, _Azure_)
`DATA_LUNCH_OAUTH_SECRET` | _str_ | ❌ | _OAuth secret_ used for configuring the OAuth provider (_GitHub_, _Azure_)
`DATA_LUNCH_OAUTH_REDIRECT_URI` | _str_ | ❌ | _OAuth redirect uri_ used for configuring the OAuth provider (_GitHub_, _Azure_), do not set to use default value
`DATA_LUNCH_OAUTH_TENANT_ID` | _str_ | ❌ | _OAuth tenant id_ used for configuring the OAuth provider (_Azure_), do not set to use default value
`DATA_LUNCH_DB_USER` | _str_ | ❌ | _Postgresql_ user, do not set to use default value
`DATA_LUNCH_DB_PASSWORD` | _str_ | ❌ | _Postgresql_ password
`DATA_LUNCH_DB_HOST` | _str_ | ❌ | _Postgresql_ host, do not set to use default value
`DATA_LUNCH_DB_PORT` | _str_ | ❌ | _Postgresql_ port, do not set to use default value
`DATA_LUNCH_DB_DATABASE` | _str_ | ❌ | _Postgresql_ database, do not set to use default value
`DATA_LUNCH_DB_SCHEMA` | _str_ | ❌ | _Postgresql_ schema, do not set to use default value

### 2.4. Manually install the development environment
> [!WARNING]
> This step is not required if the [setup script](#22-setup-the-development-environment) (`setup_dev_env.sh`) is used.

Use the terminal for navigating to the repository base directory.\
Use the following command in your terminal to create an environment named `data-lunch` manually.  
Otherwise use the [setup script](#22-setup-the-development-environment) to activate the guided installing procedure.

```
conda env create -f environment.yml
```

Activate the new _Conda_ environment with the following command.

```
conda activate data-lunch
```

### 2.5. Manually install data-lunch CLI

> [!WARNING]
> This step is not required if the [setup script](#22-setup-the-development-environment) (`setup_dev_env.sh`) is used.

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

### 2.6. Running the docker-compose system

Since this app will be deployed with an hosting service a _Dockerfile_ to build a container image is available.  
The docker compose file (see `docker-compose.yaml`) deploys the web app container along with a _load balancer_ (the _nginx_ container)
to improve the system scalability.

Look inside the `makefile` to see the `docker` and `docker-compose` options.

To build and run the dockerized system you have to install [Docker](https://docs.docker.com/get-docker/).  
Call the following `make` command to start the build process.

```
make docker-up-init docker-up-build
```

`up-init` initialize the _ssl certificate_ based on the selected environment (as set in the environment variable `PANEL_ENV`, i.e. _development_ or _production_).  
Call only `make` (without arguments) to trigger the same command.  
A missing or incomplete _ssl certificate folder_ will result in an `nginx` container failure on start-up.

Images are built and the two containers are started.  

You can then access your web app at `http://localhost:PORT` (where `PORT` will match the value set through the environment variable).

> [!NOTE]
> You can also use `make docker-up` to spin up the containers if you do not need to re-build any image or initialize ssl certificate folders.

> [!IMPORTANT]
> An additional container named `db` is started if `db=postgresql` is set

### 2.7. Running a single container

It is possible to launch a single server by calling the following command.

```
make docker-build

make docker-run
```

You can then access your web app at `http://localhost:5000` (if the deafult `PORT` is selected).

### 2.8. Running locally

Launch a local server with default options by calling the following command.

```
python -m dlunch
```

Use _Hydra_ arguments to alter the app behaviour.

```
python -m dlunch server=basic_auth
```

See [Hydra's documentation](https://hydra.cc/docs/intro/) for additional details.

## 3. Additional installations before contributing

> [!WARNING]
> This step is not required if the [setup script](#22-setup-the-development-environment) (`setup_dev_env.sh`) is used.

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

> [!WARNING]
> This step is not required if the [setup script](#22-setup-the-development-environment) (`setup_dev_env.sh`) is used.

The _Commitizen_ hook checks that rules for _conventional commits_ are respected in commits messages.
Use the following command to enjoy _Commitizen's_ interactive prompt.

```
conda activate commitizen
cz commit
```

`cz c` is a shorther alias for `cz commit`.

## 4. Release strategy from `development` to `main` branch

> [!CAUTION]
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

> [!WARNING]
> This step is not required if the [setup script](#22-setup-the-development-environment) (`setup_dev_env.sh`) is used.

The makefile has two rules for conviniently setting up and removing authentication credentials for _Google Cloud Platform_ command line interface: `gcp-config` and `gcp-revoke`.