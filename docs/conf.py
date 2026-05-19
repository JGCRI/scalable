# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

sys.path.insert(0, os.path.abspath('..'))
sys.path.insert(0, os.path.abspath('../scalable'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Scalable'
copyright = '2026, Battelle Memorial Institute'
author = 'Shashank Lamba, Pralit Patel, Chris Vernon'

# Pull the release version from the installed package metadata so the docs
# stay in sync with pyproject.toml's [project.version] without having to be
# updated by hand.
try:
    from importlib.metadata import version as _pkg_version

    release = _pkg_version("scalable")
except Exception:  # pragma: no cover - allow building from a source checkout
    release = "0.0.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx.ext.autodoc", "sphinx.ext.todo", "sphinx.ext.viewcode", "sphinx.ext.napoleon"]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': False,
    'special-members': '__init__',
    'inherited-members': False,
    'show-inheritance': False,
    'no-index': True,
}

# add_module_names = False

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_title = 'Scalable Documentation'
html_logo = 'images/scalable_logo_nobkg.png'
html_theme_options = {
    'sidebar_hide_name': True,
}

# GitHub Pages compatibility
html_baseurl = 'https://jgcri.github.io/scalable/'
