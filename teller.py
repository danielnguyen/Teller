import os
import argparse
import logging
import mariadb
import sqlite3
import sys

from teller import pdf_processor
from teller import db_manager

DEBUG=False

LOGFILE='/home/danielnguyen/Teller/Teller.log'
LOGFORMAT = '%(asctime)s : %(message)s'

def main():
    logger = logging.getLogger("Teller")

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-t', '--db-type', dest='db_type', choices=['MARIADB', 'SQLITE'], default='SQLITE')
    arg_parser.add_argument('-n', '--db-name', dest='db_name', default='teller')
    arg_parser.add_argument('-H', '--db-host', dest='db_host')
    arg_parser.add_argument('-u', '--db-username', dest='db_username')
    arg_parser.add_argument('-p', '--db-password', dest='db_password')
    arg_parser.add_argument('-P', '--db-port', dest='db_port')
    arg_parser.add_argument('-d', '--pdf-dir', dest='directory', default='statements')
    args = arg_parser.parse_args()

    if args.directory:
        assert os.path.exists(args.directory)
        directory = args.directory

    if args.db_type == 'MARIADB':
        if (args.db_username and args.db_password and args.db_host and args.db_port):
            try:
                conn = mariadb.connect(
                    user=args.db_username,
                    password=args.db_password,
                    host=args.db_host,
                    port=int(args.db_port),
                    autocommit=True,
                    database=args.db_name
                )
            except mariadb.Error as e:
                logger.error("Error connecting to MariaDB Platform: " + e)
                sys.exit(1)

            cursor = conn.cursor()     
        else:
            logger.error("Error connecting to MariaDB: missing configuration")
            sys.exit(1)
    elif args.db_type == 'SQLITE':
        cursor = sqlite3.connect(f"{args.db_name}.db")
    else:
        logger.error("Error connecting to database: Unknown DB Type provided (" + args.db_type + ")")
        sys.exit(1)

    with cursor:

        try:
            db_manager.create_table(cursor)
        except (mariadb.Error, sqlite3.OperationalError):  # db exists
            pass

        logger.info("Searching for pdfs in '" + directory + "'...")
        found_trans = pdf_processor.get_transactions(directory) 
        if len(found_trans) > 0:
            logger.debug("Found " + str(len(found_trans)) + " transactions in pdf statements") 
            to_add = found_trans

            existing_trans = db_manager.get_transactions(cursor)
            # Remove existing transactions
            if existing_trans is not None:
                to_add = to_add - existing_trans

            logger.info("Adding " + str(len(to_add)) + " new transactions to db...")
            db_manager.add_transactions(cursor, to_add)
        else:
            logger.info("No new transactions found.")


if __name__ == '__main__':
    logging.basicConfig(filename=LOGFILE, level=logging.DEBUG, format=LOGFORMAT)
    main()

