from datetime import datetime
from .model import Transaction, AccountType

def create_table(db_conn):
    db_conn.execute(
        """
        CREATE TABLE transactions (
            id INTEGER AUTO_INCREMENT PRIMARY KEY,
            account_type varchar(255),
            account_number varchar(255),
            timestamp varchar(255),
            description varchar(255),
            amount REAL
        )
        """
    )

def add_transactions(db_conn, transactions):
    for t in transactions:
        db_conn.execute(
            """
            INSERT INTO transactions
            (account_type, account_number, timestamp, description, amount)
            VALUES 
            (?, ?, ?, ?, ?)
            """,
            [t.account_type.value,
             t.account_number,
             t.date,
             t.description,
             t.amount]
        )

def get_transactions(db_conn):
    res = db_conn.execute(
        """
        SELECT account_type,
               account_number,
               timestamp,
               description,
               amount
        FROM transactions
        """
    )
    if res is not None:
        existing_rows = res.fetchall()

        existing_trans = {Transaction(AccountType(e[0]), 
                                    e[1],
                                    e[2],
                                    e[3],
                                    e[4])
                        for e in existing_rows}
        return existing_trans
