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
