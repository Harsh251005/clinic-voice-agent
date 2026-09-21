"""Persistence. The only package that imports SQLAlchemy.

Agent tools and the dashboard both go through `repo`, so there is exactly one
definition of every query. Swapping SQLite for Postgres is a DATABASE_URL
change; nothing outside this package notices.
"""
