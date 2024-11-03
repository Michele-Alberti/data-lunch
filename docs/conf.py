# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Data-Lunch"
copyright = "2024, Michele Alberti"
author = "Michele Alberti"
release = "v3.3.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.graphviz",
    #    "sphinxext.rediraffe",
    #    "sphinx_design",
    #    "sphinx_copybutton",
    "autoapi.extension",
    # For extension examples and demos
    "myst_parser",
    #    "ablog",
    #    "jupyter_sphinx",
    #    "nbsphinx",
    #    "numpydoc",
    #    "sphinx_togglebutton",
    #    "jupyterlite_sphinx",
    "sphinx_favicon",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "**.ipynb_checkpoints"]

intersphinx_mapping = {
    "sphinx": ("https://www.sphinx-doc.org/en/master", None)
}

# -- MyST options ------------------------------------------------------------

# This allows us to use ::: to denote directives, useful for admonitions
myst_enable_extensions = ["colon_fence", "linkify", "substitution"]
myst_heading_anchors = 2
# myst_substitutions = {"rtd": "[Read the Docs](https://readthedocs.org/)"}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
# html_logo = "_static/logo.png"
html_favicon = "_static/favicon.ico"

html_theme_options = {
    "logo": {
        "text": "Data-Lunch Documentation",
        "image_light": "_static/logo-light.png",
        "image_dark": "_static/logo-dark.png",
    },
    "header_links_before_dropdown": 4,
    "show_toc_level": 2,
    "navbar_align": "left",  # [left, content, right] For testing that the navbar items align properly
    # "show_nav_level": 2,
    "footer_start": ["copyright"],
    "footer_center": ["sphinx-version"],
    # "back_to_top_button": False,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
# html_css_files = ["custom.css"]
# html_js_files = ["pydata-icon.js", "custom-icon.js"]
# todo_include_todos = True

# -- favicon options ---------------------------------------------------------

# see https://sphinx-favicon.readthedocs.io for more information about the
# sphinx-favicon extension
favicons = [
    # generic icons compatible with most browsers
    #    "favicon-32x32.png",
    #    "favicon-16x16.png",
    {"rel": "shortcut icon", "sizes": "any", "href": "favicon.ico"},
    # chrome specific
    #    "android-chrome-192x192.png",
    # apple icons
    #    {"rel": "mask-icon", "color": "#459db9", "href": "favicon.ico"},
    #    {"rel": "apple-touch-icon", "href": "favicon.ico"},
    # msapplications
    #    {"name": "msapplication-TileColor", "content": "#459db9"},
    #    {"name": "theme-color", "content": "#ffffff"},
    #    {"name": "msapplication-TileImage", "content": "mstile-150x150.png"},
]

# -- Options for autosummary/autodoc output ------------------------------------
autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "groupwise"

# -- Options for autoapi -------------------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../dlunch"]
autoapi_keep_files = True
autoapi_root = "api"
autoapi_member_order = "groupwise"
