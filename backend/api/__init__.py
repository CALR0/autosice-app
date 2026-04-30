"""API package for backend endpoints.

This package will hold route blueprints and validators. Files are lightweight
placeholders so we can incrementally move endpoints here later.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__)

__all__ = ["api_bp"]
