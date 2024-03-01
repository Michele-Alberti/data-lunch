## v2.12.0 (2024-03-01)

### Feat

- **panel/gui/backup.yaml**: add a gui theme for backup server

### Refactor

- **panel/gui/major_release.yaml**: improve gui theme for major release

## v2.11.2 (2024-03-01)

### Fix

- **models.py**: fix error in server default for date in stats table

## v2.11.1 (2024-02-28)

### Fix

- **db/postgresql.yaml**: fix error in stats query

## v2.11.0 (2024-02-24)

### Feat

- **gui.py**: improve columns layout in backend

## v2.10.0 (2024-02-23)

### Feat

- add flag to activate/deactivate database creation

## v2.9.1 (2024-02-04)

### Fix

- **Dockerfile.web**: remove reference to unofficial package repo

## v2.9.0 (2024-02-04)

### Feat

- move health endpoint from custom page to liveness endpoint
- add a banner shown when no menu is available

## v2.8.0 (2024-01-27)

### Feat

- **__main__.py**: add an /health endpoint
- add azure as oauth provider and improve config files to handle different auth approaches

### Fix

- **cli.py**: fix error in __version__ evaluation
- **auth.py-is_basic_auth_active**: fix error when returning the result of is_basic_auth_active
- fix reference to psw_special_chars

### Refactor

- **package-name**: change package name from data_lunch_app to dlunch

## v2.7.0 (2024-01-02)

### Feat

- **core.py**: change no_more_orders toggle button visibility and enabklement for guest users
- add flag that disable guest users' (i.e. unprivileged users) authorization
- move other info to user tab and add additional info (username and user group)
- **gui.py**: avoid guest users to store guest override flag in cache
- add retries when creating a database
- add support for postgresql as database manager
- add guest override toggle (frontend) and clear cache button (backend)
- add authorization callback
- add buttons to app header for logout/backend redirect in 'main' and exit redirect in 'backend' page
- implement authorized users and guests management through database tables
- improve web app behavior based on auth provider and improve code readability
- **server-config-files**: add a non authenticated config as default for server
- **html-templates**: add auth error template and improve login and logout templates
- add support for github oauth provider

### Fix

- fix error in sidbar tabs refresh when using guest override and fix an error in other info text
- **guest_override-cache**: move guest override from cache to db and collect some sql related calls inside models.py's classes
- **basic-auth**: fix error that  caused encrypted password to be saved for every guest user
- **auth/default.yaml**: fix error due to relocation of psw_special_chars
- fix missing schema in pandas.DataFrame.to_sql commands and add hydra args to command line
- **__main__.py**: add database initialization in main function for basic auth
- **auth.py**: fix error in current user retrieval for  authorize callback function
- **__init__.py**: remove set panel config from backend (already in __main__.py)
- **github_oauth.yaml**: fix github auth provider to work with docker compose on localhost
- **cloud.py**: change get_bucket_list to get_gcloud_bucket_list

### Refactor

- refactor salad menu to use jinja
- change variables named 'auth_user(s)' to 'privileged_user(s)'
- move basic auth password and guest user config from panel to auth config file
- change all 'add_auth_user' in variables and function names to 'add_privileged_user'
- replaced hardcoded table names with reference to tables declared in models.py
- replace SQLAlchemy v1.x expressions with v2.x equivalent
- **db-config-files**: refactor config file to have a distinct config for sqlite driver
- change all reference to 'authorized user' in 'privileged user'
- move oauth redirect uri to DATA_LUNCH_OAUTH_REDIRECT_URI env variable
- **server-config-files**: rename default.yaml and basic_oauth.yaml

### Perf

- **guest_override**: sidebar is not reloaded every time because sidebar tabs does not change with guest_override
- update sqlalchemy to v2.0.23
- **cli.py**: remove cache command group from command line

## v2.6.0 (2023-09-29)

### Feat

- **gui.py**: add icons to 'build menu' and 'download xlsx' buttons
- **core.py**: add number of people to excel file exported by download_dataframe

### Refactor

- move shared data folder creation to models.py

## v2.5.0 (2023-08-20)

### Feat

- move credentials from json file to database
- add backend dashboard for managing users credentials

### Fix

- fix oauth_encryption_key and oauth_expiry usage
- remove scheduled task 'credentials upload'
- adapt gui and support code (cli, scripts, scheduled tasks) to the new credential system

## v2.4.3 (2023-08-01)

### Fix

- hotfix for guest user password problem

## v2.4.2 (2023-08-01)

### Fix

- fix encoding in password handling

## v2.4.1 (2023-07-31)

### Fix

- use BEGIN EXCLUSIVE transaction for setting the guest user password

## v2.4.0 (2023-07-31)

### Feat

- add set_guest_user_password function to set or reset guest user password

### Fix

- move guest user password creation from __main__.py to __init__.py

## v2.3.2 (2023-07-27)

### Fix

- **gui.py**: remove rf string from guest password widget

## v2.3.1 (2023-07-27)

### Fix

- fix configuration for current directory, password special char and auth expiry

## v2.3.0 (2023-07-26)

### Feat

- move guest credentials from email to password tab

### Fix

- **auth.py**: fix error in generated password length

## v2.2.1 (2023-07-25)

### Fix

- remove password escaping in email scripts

## v2.2.0 (2023-07-25)

### Feat

- add jinja template for ip and users emails

### Fix

- **create_users_from_lists.py**: fix error in MIME object creation

## v2.1.0 (2023-07-21)

### Feat

- add credentials upload to scheduled tasks in panel config files
- add support for authenticated users and guests
- **cloud.py**: add upload from string and download as bytes to GCP platform support functions
- **cli.py**: add list users command to cli
- **auth.py**: add password generator, logout function and list user function
- **cli.py**: add authentication credentials management to the cli
- add simple authentication
- **no_sched_clean.yaml**: add panel config file with scheduled cleaning deactivated

### Fix

- fix credentials.json path in config
- **auth.py**: move credentials.json into the folder shared_data
- **login.html**: fix title and favicon of login page

## v2.0.0 (2023-06-06)

### BREAKING CHANGE

- update panel to version 1.0.4 introducing the shadow DOM approach for panel widgets

### Feat

- **gui.py**: improve button flexbox and remove stretch from menu flexbox
- add config for major_release (gui) and a new favicon
- update environments to python 3.11 including a breaking change to panel library

## v1.21.0 (2023-05-14)

### Feat

- add upload database to gcp storage to config files

## v1.20.1 (2023-04-26)

### Fix

- **gui.py**: add anonymous crossorigin to fontawesome script

### Refactor

- remove unused gcp features and improve 'all' label in makefile

## v1.20.0 (2023-03-12)

### Feat

- add salad menu
- **quotes.xlsx**: add new quotes

## v1.19.1 (2023-03-07)

### Fix

- **core.py**: fix bug caused by takeaway orders under specific circumstances

## v1.19.0 (2023-03-05)

### Feat

- add special graphic configurations

### Refactor

- move graphic interface configurations to a dedicated sub-config file

## v1.18.0 (2023-03-01)

### Feat

- add flag for takeaway meals

### Fix

- fix error in create_app logic

### Refactor

- **gui.py**: remove unused emoji html strings
- move all graphic elements to a dedicated module
- **send_email_with_ip.py**: improve script for email with vm external ip

## v1.17.0 (2023-02-05)

### Feat

- **cli.py**: add clean caches command to cli

### Fix

- fix clean_tables functions and improve get_flag function
- **__init__.py**: fix import error
- move the 'no_more_orders' flag from pn.cache to a dedicated database table

## v1.16.0 (2023-01-25)

### Feat

- add custom favicon

### Fix

- **core.py**: restore note row in tables with orders

### Perf

- add font-awesome icons from js file

## v1.15.0 (2023-01-22)

### Feat

- remove unselected items from orders' tables

### Fix

- fix scroll for large tables inside orders' section

### Perf

- add compression to server response

## v1.14.2 (2022-12-08)

### Fix

- read docker image version from environment variable

## v1.14.1 (2022-12-08)

### Fix

- **compose_init.sh**: add escaped " to string

## v1.14.0 (2022-12-08)

### Feat

- **compose_init.sh**: add environment variable for DDNS url

## v1.13.0 (2022-12-07)

### Feat

- **cli.py**: add export and load commands for tables
- **models.py**: add defaults value also server-side (sqlite DDLs)

### Fix

- **panel/default.yaml**: fix an error inside the query for stats table

## v1.12.0 (2022-12-07)

### Feat

- add icon in orders tables to highlight that an user is a guest
- add support for guest users
- **__init__.py**: group and improve custom css, force fixed with inside sidebar

### Fix

- **core.py**: move create_session in reload_menu outside if statements

## v1.11.0 (2022-12-04)

### Feat

- add host info inside the stats tab

### Fix

- **compose_init.sh**: fix error in cronjob command

## v1.10.3 (2022-12-04)

### Fix

- use pyproject.toml as config file for package build and fix cli.py

## v1.10.2 (2022-12-03)

### Fix

- **default.yaml**: fix error in stats query
- **core.py**: fix bug with stats table index and turn stats and order tables to non-editable

## v1.10.1 (2022-11-27)

### Fix

- **core.py**: fix error that ignored the "no more order" constraint if set by another user

## v1.10.0 (2022-11-27)

### Perf

- change widgets layout to improve performances
- **server/development.yaml**: remove threading

### Feat

- add "stop orders" button to lock orders' table
- add notifications as replacement for messages inside modal window

### Fix

- **__init__.py**: fix error in panel threading configuration

## v1.9.4 (2022-11-16)

### Fix

- **.pre-commit-config.yaml**: fix error in pre-commit config file

## v1.9.3 (2022-11-13)

### Fix

- **core.py**: fix error in check conditions for delete_order

## v1.9.2 (2022-11-13)

### Fix

- fix dockerfile forcing web:latest and delete orders in addition to user in delete_order

## v1.9.1 (2022-11-12)

### Fix

- fix errors in docker-compose.yaml and makefile

## v1.9.0 (2022-11-12)

### Fix

- remove print from cli.py and deactivate scheduled cleaning

### Feat

- **cli.py**: add commands to command line interface
- add stats tab and famous quotes about food
- add notes and lunch time recap column

## v1.8.0 (2022-10-23)

### Feat

- **send_email_with_ip.py**: add script for emails with vm external ip

## v1.7.3 (2022-10-22)

### Fix

- **compose_init.sh**: add dhparams installation

## v1.7.2 (2022-10-22)

### Fix

- fix errors in makefile and compose_init.sh

## v1.7.1 (2022-10-22)

### Fix

- fix missing image extension (.jpeg) and download of empty order list

## v1.7.0 (2022-10-21)

### Feat

- add support for https and ssl certificates

## v1.6.2 (2022-10-19)

### Fix

- change container and load balancer port to 80

## v1.6.1 (2022-10-19)

### Fix

- **db/production.yaml**: fix error in shared_data path
- fix non-breaking error on makefile and production.yaml
- **nginx.conf**: change listen port to 8080
- **makefile**: fix error in run-it label

## v1.6.0 (2022-10-18)

### Feat

- add ocr to build_menu

## v1.5.0 (2022-10-16)

### Feat

- download the sqlite database from a bucket on google cloud storage

### Refactor

- improve scheduled tasks execution

### Fix

- **CPU_Memory_time.ipynb**: fix error in df_info instantiation

## v1.4.1 (2022-10-15)

### Refactor

- **panel/default.yaml**: change hour of scheduled_cleaning to 15

## v1.4.0 (2022-10-14)

### Feat

- add scheduled cleaning of menu files and database tables

## v1.3.2 (2022-10-14)

### Fix

- install data-lunch environment at os level

## v1.3.1 (2022-10-13)

### Fix

- **core.py**: fix error in call to read_excel

## v1.3.0 (2022-10-13)

### Feat

- **conf/panel/default.yaml**: add salads auto-inserted items

## v1.2.1 (2022-10-13)

### Fix

- **core.py**: fix non-relative path error in container

## v1.2.0 (2022-10-13)

### Fix

- **models.py**: fix minor bugs and add event listner

### Feat

- add results table to main panel  and a delete order button

## v1.1.1 (2022-10-12)

### Fix

- **core.py**: remove old functions

## v1.1.0 (2022-10-11)

### Feat

- add support for google cloud app engine

## v1.0.1 (2022-10-09)

### Fix

- **makefile**: fix errors in container names

## v1.0.0 (2022-10-09)
