"""Package with Hydra configuration yaml files.

The following Hydra configuration groups ae available:

* `panel`: main Panel configurations (text used in menu and tables, scheduled tasks, other graphic user interface options).
* `db`: database dialect (sqlite or postgresql) and specific queries, upload of db to external storage (sqlite only), db table creation at start-up.
* `server`: Panel server options and server-level authentication options (basic auth or OAuth).
* `auth`: main authentication and authorization options.
* `basic_auth`: optional configuration group that add configurations required by basic authentication.
* `hydra/job_logging`: override Hydra default logging handlers.

"""
