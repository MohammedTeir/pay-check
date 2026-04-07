"""
Production WSGI entry point for the Flask webapp.
Used by gunicorn in production deployments.
"""

from webapp.app import app

if __name__ == "__main__":
    app.run()
