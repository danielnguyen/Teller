import os
import argparse
import mariadb
import sqlite3
import sys

from teller import pdf_processor
from teller import db_manager


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('database')
    arg_parser.add_argument('-d', dest='directory', required=False)
    args = arg_parser.parse_args()

    directory = 'statements'

    if args.directory:
        assert os.path.exists(args.directory)
        directory = args.directory

    db_type = os.environ.get('DB_TYPE') # One of DatabaseType
    
    if (db_type == 'MARIADB'):
        username = os.environ.get('DB_USERNAME')
        password = os.environ.get('DB_PASSWORD')
        host = os.environ.get('DB_HOST')
        port = os.environ.get('DB_PORT')
        db_name = os.environ.get('DB_NAME')

        req_params = username and password and host and port and db_name

        if (req_params):
            # Connect to MariaDB Platform
            try:
                conn = mariadb.connect(
                    user="db_user",
                    password="db_user_passwd",
                    host="192.0.2.1",
                    port=3306,
                    database="employees"

                )
            except mariadb.Error as e:
                print(f"Error connecting to MariaDB Platform: {e}")
                sys.exit(1)

            # Get Cursor
            db_conn = conn.cursor()
        else:
            print(f"Error connecting to MariaDB: missing configuration")
            sys.exit(1)
    elif (db_type == 'SQLITE'):
        db_conn = sqlite3.connect(args.database)
        try:
            db_manager.create_db(db_conn)
        except sqlite3.OperationalError:  # db exists
            pass
    else:
        print(f"Error connecting to database: Environment Variable 'DB_TYPE' not defined.")
        sys.exit(1)

    if db_conn is None:
        print(f"Error connecting to database.")
        sys.exit(1)

    print(f"Searching for pdfs in '{directory}'...")
    found_trans = pdf_processor.get_transactions(directory) 
    print(f"Found {len(found_trans)} transactions in pdf statements") 

    existing_trans = db_manager.get_existing_trans(db_conn)
    to_add = found_trans - existing_trans

    print(f"Adding {len(to_add)} new transactions to db...")
    db_manager.add_to_db(db_conn, to_add)


if __name__ == '__main__':
    main()

