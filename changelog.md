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
