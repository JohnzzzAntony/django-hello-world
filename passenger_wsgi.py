import sys, os

# Set up paths for Hostinger/Phusion Passenger
# Absolute path to your subdomain folder
PROJECT_ROOT = "/home/u933834587/domains/creativegradientz.com/public_html/admin_site"

# Path to your project-specific python interpreter
INTERP = os.path.join(PROJECT_ROOT, "venv/bin/python")

if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.append(PROJECT_ROOT)

# Point to your Django project's wsgi module
from jkr.wsgi import application
