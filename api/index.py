"""Vercel entry point.

Vercel's Python runtime looks for a WSGI callable named ``app`` in this module.
"""

from photo_portfolio.wsgi import application as app  # noqa: F401
