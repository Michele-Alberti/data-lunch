# Data Lunch <!-- omit in toc -->

The ultimate web app for a well organized lunch.

## Table of contents

- [Table of contents](#table-of-contents)
- [Development environment setup](#development-environment-setup)
  - [Miniconda](#miniconda)
  - [Setup the development environment](#setup-the-development-environment)
  - [Environment variables](#environment-variables)
    - [General](#general)
    - [Docker and Google Cloud Platform](#docker-and-google-cloud-platform)
    - [TLS/SSL Certificate](#tlsssl-certificate)
    - [Encryption and Authorization](#encryption-and-authorization)
  - [Manually install the development environment](#manually-install-the-development-environment)
  - [Manually install data-lunch CLI](#manually-install-data-lunch-cli)
  - [Running the docker-compose system](#running-the-docker-compose-system)
  - [Running a single container](#running-a-single-container)
  - [Running locally](#running-locally)
- [Additional installations before contributing](#additional-installations-before-contributing)
  - [Pre-commit hooks](#pre-commit-hooks)
  - [Commitizen](#commitizen)
- [Release strategy from `development` to `main` branch](#release-strategy-from-development-to-main-branch)
- [Google Cloud Platform utilities](#google-cloud-platform-utilities)

<!-- DO NOT REMOVE THIS ANCHOR -->
<!-- Used by MkDocs generate_getting_started.py -->
<a id="doc-start"></a>

## Introduction

_Data-Lunch_ is a web app to help people managing lunch orders.  
The interface make possible to upload a menu as an Excel file or as an image. The menu is copied inside the app and people are then able to place orders at preset lunch times.  
Users can flag an order as a takeway one, and, if something change, they can move an order to another lunch time (or change its takeaway status).

The systems handle _guests_ users by giving them a limited ability to interact with the app (they can in fact just place an order).

Once all order are placed it is possible to stop new orders from being placed and download an Excel files with every order, grouped by lunch time and takeaway status.

The idea behind this app is to simplify data collection at lunch time, so that a single person can book a restaurant and place orders for a group of people (friends, colleagues, etc.).

> [!IMPORTANT]
> This section is a work in progress, the app has a lot of configurations, not yet described in this documentation.  
> Authentication and guest management are just examples of what is missing from this documentation. 


## Installation

Install commitizen using `pip`:

```
 pip install dlunch
```

For the program to work properly you need the following system dipendencies:

  - [SQLite](https://www.sqlite.org/): used if you set the database to `sqlite`.
  - [Tesseract](https://github.com/tesseract-ocr/tesseract): used to convert images with menu to text.

If you need help on how to install those system preferences on linux (_Debian_) you can check the file `docker/web/Dockerfile.web`.  
It shows how to install them with `apt`.

## Usage

Before starting you need the following environment variables to avoid errors on _Data-Lunch_ startup.

### Environment variables

> [!IMPORTANT]
> `DATA_LUNCH_COOKIE_SECRET` and `DATA_LUNCH_OAUTH_ENC_KEY` are required even if `server=no_auth` is set.

> [!TIP]
> Use the command `data-lunch utils generate-secrets` to generate a valid secret.

| Variable | Type | Required | Description |
|----------|:----:|:--------:|-------------|
`PANEL_ENV` | _str_ | ✔️ | Environment, e.g. _development_, _quality_, _production_, affects app configuration (_Hydra_)
`PORT` | _int_ | ❌ | Port used by the web app (or the container), default to _5000_; affects app configuration (it is used by _Hydra_)
`DATA_LUNCH_COOKIE_SECRET` | _str_ | ✔️ | _Secret_ used for securing the authentication cookie (use `data-lunch utils generate-secrets` to generate a valid secret); leave it as an empty variable if no authentication is set
`DATA_LUNCH_OAUTH_ENC_KEY` | _str_ | ✔️ | _Encription key_ used by the OAuth algorithm for encryption (use `data-lunch utils generate-secrets` to generate a valid secret); leave it as an empty variable if no authentication is set

> [!NOTE]
> The following variables are just a small part of the total. See [here][environment-variables] for more details.

### Launch command
Use the following command to start the server with default configuration (_SQLite_ database, no authentication):

```
python -m dlunch
```

Connect to localhost:5000 (if the default port is used) to see the web app.

## Customization
_Data-Lunch_ configurations explout [Hydra](https://hydra.cc/docs/intro/) versatility.
It is possible to alter default configurations by using _Hydra's overrides_, for example

```
python -m dlunch panel/gui=major_release
```

will alter some graphic elements to show a release banner.

## Docker
A _Docker_ image with Data-Lunch is available [here](https://hub.docker.com/r/michelealberti/data-lunch-app).
