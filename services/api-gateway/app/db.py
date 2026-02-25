import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def db_conn():
    return psycopg2.connect(DATABASE_URL)