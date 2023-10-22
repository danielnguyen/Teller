from enum import Enum

class AccountType(Enum):
    AMEX = 'AMEX'
    TD = 'TD'
    MFC = 'MFC'
    RBC = 'RBC'
    BMO = 'BMO'
    BMO_2022 = 'BMO_2022'
    
class Transaction():
    def __init__(self, account_type, account_number, date, description, amount):
        self.account_type = account_type
        self.account_number = account_number
        self.date = date
        self.description = description
        self.amount = amount

    def __hash__(self):
        return hash((self.description,
                     self.amount, 
                     self.date, 
                     self.account_number, 
                     self.account_type))
    
    def __eq__(self, other):
        return isinstance(other, Transaction) and \
               self.account_type == other.account_type and \
               self.date == other.date and \
               self.description == other.description and \
               self.account_number == other.account_number and \
               self.amount == other.amount

    def __repr__(self):
        return (f"({self.amount}, "
                f"{self.date}, "
                f"{self.account_type.value}, "
                f"{self.account_number}, "
                f"{self.description})")
