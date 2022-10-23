# Data Lunch <!-- omit in toc -->

The ultimate web app for a well organized lunch.

## 1. Table of contents

- [1. Table of contents](#1-table-of-contents)
- [2. Development environment setup](#2-development-environment-setup)
  - [2.1. Miniconda](#21-miniconda)
  - [2.2. Environment variables](#22-environment-variables)
  - [2.3. Install data-lunch CLI](#23-install-data-lunch-cli)
  - [2.4. Running the docker-compose system](#24-running-the-docker-compose-system)
  - [2.5. Running a single container](#25-running-a-single-container)
- [3. Additional installations before contributing](#3-additional-installations-before-contributing)
  - [3.1. Pre-commit hooks](#31-pre-commit-hooks)
  - [3.2. Commitizen](#32-commitizen)
- [4. Release strategy from `development` to `main` branch](#4-release-strategy-from-development-to-main-branch)
- [5. Deployment With Google Cloud App Engine](#5-deployment-with-google-cloud-app-engine)

## 2. Development environment setup

The following steps will guide you through the installation procedure.

### 2.1. Miniconda

[<img style="position: relative; bottom: 3px;" src="https://docs.conda.io/en/latest/_images/conda_logo.svg" alt="Conda" width="80"/>](https://docs.conda.io/en/latest/) is required for creating the development environment (it is suggested to install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)).

From terminal navigate to the repository base directory.\
Use the following command in your terminal to create an environment named `trails-app`.

```
conda env create -f environment.yml
```

Activate the new _Conda_ environment with the following command.

```
conda activate trails-app
```
### 2.2. Environment variables

The following environment variables are required for running the _web app_ or the _makefile_.
| Variable | Type | Example Value |
|----------|:------:|-------|
`PANEL_APP` | _str_ | data-lunch-app (used by `makefile`)
`PANEL_ENV` | _str_ | development
`PORT` | _int_ | 5000
`DOCKER_USERNAME` | _str_ | your _Docker Hub_ username (used by `makefile`)
`GCLOUD_PROJECT` | _str_ | _Google Cloud Platform_ `project_id` (used by `makefile`)
`CERT_EMAIL` | _str_ | email for _SSL certificates_
`DOMAIN` | _str_ | domain name, e.g. mywebapp.com
`MAIL_USER` | _str_ | email client user (for sending emails with the current instance IP)
`MAIL_APP_PASSWORD` | _str_ | email client user (for sending emails with the current instance IP)
`MAIL_RECIPIENTS` | _str_ | email recipients as string, separated by `,` (for sending emails with the current instance IP)


### 2.3. Install data-lunch CLI

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

### 2.4. Running the docker-compose system

Since this app will be deployed with an hosting service a _Dockerfile_ to build a container image is available.  
The docker compose file (see `docker-compose.yaml`) builds the web app container along with a _load balancer_ (the _nginx_ container)
to improve the system scalability.

Look inside the `makefile` to see the `docker` and `docker-compose` options.

To build and run the dockerized system you have to install [Docker](https://docs.docker.com/get-docker/).  
Call the following `make` command to start the build process.

```
make up-build
```

The two images are built and the two containers are started.  

You can then access your web app at `http://localhost:4000`.

> **Note:**  
> You can also use `make up` to spin up the containers if you do not need to re-build any image.

### 2.5. Running a single container

It is possible to launch a single server by calling the following command.

```
make build

make run
```

You can then access your web app at `http://localhost:5000`.

## 3. Additional installations before contributing

Before contributing please create the `pre-commit` and `commitizen` environments.

```
cd requirements
conda env create -f pre-commit.yml
conda env create -f commitizen.yml
```

### 3.1. Pre-commit hooks

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

The _Commitizen_ hook checks that rules for _conventional commits_ are respected in commits messages.
Use the following command to enjoy _Commitizen's_ interactive prompt.

```
conda activate commitizen
cz commit
```

`cz c` is a shorther alias for `cz commit`.

## 4. Release strategy from `development` to `main` branch

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

## 5. Deployment With Google Cloud App Engine

To deploy the repository on _Google's App Engine_ a requirement.txt is needed.  
Use the following commands.

```
conda activate data-lunch
pip list --format=freeze > requirements.txt
```