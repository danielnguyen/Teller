import re
import pdfplumber

from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from teller.model import Transaction, AccountType

overrideDuplicates = True # True = assume all 'duplicate' transactions are valid
debug = False # prints out one parsed PDF for you to manually test regex on

regexes = {
    'COMMON' : {
        'accnum_cc': (r"(?P<account_number>(?:X{4} |[0-9]{4} ){3}[0-9]{4})"), # XXXX XXXX XXXX 1234 or 1234 5678 9010 1234
        'accnum_bank': (r"(?P<account_number>[0-9]{5}-[0-9]{7})") # 01234-5678987
    },
    'BMO_2022': {
        'fidetect': "^(?P<fi>BMO)",
        'txn': (r"^(?P<dates>(?:\w{3}(\.|)+ \d{1,2}\s*){2})"
            r"(?P<description>.+)\s"
            r"(?P<amount>-?[\d,]+\.\d{2})(?P<cr>(\-|\s*CR))?"),
        'startyear': r'PERIOD COVERED BY THIS STATEMENT\s\w+\.?\s{1}\d+\,\s{1}(?P<year>[0-9]{4})',
        'openbal': r'Previous Balance.*(?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'(?:New) Balance\s.*(?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?'
    },
    'BMO': {
        'fidetect': "^(?P<fi>BMO)",
        'txn': (r"^(?P<dates>(?:\w{3}(\.|)+ \d{1,2}\s*){2})"
            r"(?P<description>.+)\s"
            r"(?P<amount>-?[\d,]+\.\d{2})(?P<cr>(\-|\s*CR))?"),
        'startyear': r'Statement period\s\w+\.?\s{1}\d+\,\s{1}(?P<year>[0-9]{4})',
        'openbal': r'Previous balance.*(?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'(?:Total) balance\s.*(?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?'
    },
    'RBC': {
        'fidetect': "^(?P<fi>Royal Bank of Canada)",
        'txn': (r"(?P<dates>(?:\d{2} \w{3})) "
            r"(?P<description>.+)\s"    
            r"(?P<amount>-?\$[\d,]+\.\d{2}-?)(?P<cr>(\-|\s?CR))?"),
        'startyear': r'STATEMENT FROM .+(?P<year>-?\,.[0-9][0-9][0-9][0-9])',
        'openbal': r'Opening balance (?P<balance>[+-]?[0-9]{1,3}(?:,?[0-9]{3})*\.[0-9]{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'Closing balance [$]?(?P<balance>[+-]?[0-9]{1,3}(?:,?[0-9]{3})*\.[0-9]{2})(?P<cr>(\-|\s?CR))?'
    }, 
    'MFC': { 
        'fidetect': "^(?P<fi>Manulife)", # UNTESTED
        'txn': (r"^(?P<dates>(?:\d{2}\/\d{2} ){2})"
            r"(?P<description>.+)\s"
            r"(?P<amount>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?"),
        'startyear': r'Statement Period: .+(?P<year>-?\,.[0-9][0-9][0-9][0-9])',
        'openbal': r'(PREVIOUS|Previous) (BALANCE|Balance) (?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'(?:New) Balance (?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?'
    },
    'TD': {
        'fidetect': "^(?P<fi>TD)", # UNTESTED
        'txn': (r"(?P<dates>(?:\w{3} \d{1,2} ){2})"
            r"(?P<description>.+)\s"    
            r"(?P<amount>-?\$[\d,]+\.\d{2}-?)(?P<cr>(\-|\s?CR))?"),
        'startyear': r'Statement Period: .+(?P<year>-?\,.[0-9][0-9][0-9][0-9])',
        'openbal': r'(PREVIOUS|Previous) (STATEMENT|ACCOUNT|Account) (BALANCE|Balance) (?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'(?:NEW|CREDIT) BALANCE (?P<balance>\-?\s?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?'
    },  
    'AMEX': {
        'fidetect': "^(?P<fi>AMEX)", # UNTESTED
        'txn': (r"(?P<dates>(?:\w{3} \d{1,2} ){2})"
            r"(?P<description>.+)\s"    
            r"(?P<amount>-?[\d,]+\.\d{2}-?)(?P<cr>(\-|\s?CR))?"),
        'startyear': r'(?P<year>-?\,.[0-9][0-9][0-9][0-9])',
        'openbal': r'(PREVIOUS|Previous) (BALANCE|Balance) (?P<balance>-?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?',
        'closingbal': r'(?:New|CREDIT) Balance (?P<balance>\-?\s?\$[\d,]+\.\d{2})(?P<cr>(\-|\s?CR))?'
    },
}

def get_transactions(data_directory):
    result = set()
    for pdf_path in Path(data_directory).rglob('*.pdf'):
        try: 
            result |= _parse_pdf(pdf_path)
        except Exception as e:
            print("Error for %s" % pdf_path)
            print(e)
    return result 

def _parse_pdf(pdf_path):
    result = set()
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        print("------------------------------------------")
        print(pdf_path)
        for page in pdf.pages:
            text += page.extract_text(x_tolerance=1)

        if (debug):
            _detect_fi(text)
            print(text)
            exit()

        TARGET_FI = _detect_fi(text)

        if TARGET_FI:
            account_number = _get_account_number(text, True)
            year = _get_start_year(text, TARGET_FI)
            opening_bal = _get_opening_bal(text, TARGET_FI)
            closing_bal = _get_closing_bal(text, TARGET_FI)
            # add_seconds = 0
            
            endOfYearWarning = False

            # debugging transaction mapping - all 3 regex in 'txn' have to find a result in order for it to be considered a 'match'
            for match in re.finditer(regexes[TARGET_FI]['txn'], text, re.MULTILINE):
                match_dict = match.groupdict()
                date = match_dict['dates'].replace('/', ' ') # change format to standard: 03/13 -> 03 13
                date = date.split(' ')[0:2]  # Aug. 10 Aug. 13 -> ['Aug.', '10']
                date[0] = date[0].strip('.') # Aug. -> Aug
                date.append(str(year))
                date = ' '.join(date) # ['Aug', '10', '2021'] -> Aug 10 2021
                
                try:
                    date = datetime.strptime(date, '%b %d %Y') # try Aug 10 2021 first
                except: # yes I know this is horrible, but this script runs once if you download your .csvs monthly, what do you want from me
                    date = datetime.strptime(date, '%m %d %Y') # if it fails, 08 10 2021

                # need to account for current year (Jan) and previous year (Dec) in statements 
                endOfYearCheck = date.strftime("%m")

                if (endOfYearCheck == '12' and endOfYearWarning == False):
                    endOfYearWarning = True
                if (endOfYearCheck == '01' and endOfYearWarning):
                    date = date + relativedelta(years = 1)

                if (match_dict['cr']):
                    print("Credit balance found in transaction: '%s'" % match_dict['amount'])
                    amount = -float("-" + match_dict['amount'].replace('$', '').replace(',', ''))
                else:
                    amount = -float(match_dict['amount'].replace('$', '').replace(',', ''))

                # checks description regex
                if ('$' in match_dict['description'] and TARGET_FI != 'BMO'): # BMO doesn't have $'s in their descriptions, so this is safe 
                    print("************" + match_dict['description'])
                    newAmount = re.search(r'(?P<amount>-?\$[\d,]+\.\d{2}-?)(?P<cr>(\-|\s?CR))?', match_dict['description'])
                    amount = -float(newAmount['amount'].replace('$', '').replace(',', ''))
                    match_dict['description'] = match_dict['description'].split('$', 1)[0]

                transaction = Transaction(AccountType[TARGET_FI],
                                        account_number,
                                        str(date.date().isoformat()),
                                        match_dict['description'],
                                        amount)
                if (transaction in result):
                    if (overrideDuplicates):
                        transaction.description = transaction.description + " 2"    
                        result.add(transaction)
                    else:
                        prompt = input("Duplicate transaction found for %s, on %s for %f. Do you want to add this again? " % (transaction.description, transaction.date, transaction.amount)).lower()
                        if (prompt == 'y'):
                            transaction.description = transaction.description + " 2"    
                            result.add(transaction)
                        else:
                            print("Ignoring!")
                else:
                    result.add(transaction)

            _validate(closing_bal, opening_bal, result)
        else:
            print(f"Could not automatically detect financial institution for: {pdf_path} (skipping)")
    return result

def _validate(closing_bal, opening_bal, transactions):
    # spend transactions are negative numbers.
    # net will most likely be a neg number unless your payments + cash back are bigger than spend
    # outflow is less than zero, so purchases
    # inflow is greater than zero, so payments/cashback

    # closing balance is a positive number
    # opening balance is only negative if you have a CR, otherwise also positive
    net = round(sum([r.amount for r in transactions]), 2)
    outflow = round(sum([r.amount for r in transactions if r.amount < 0]), 2)
    inflow = round(sum([r.amount for r in transactions if r.amount > 0]), 2)
    if round(opening_bal - closing_bal, 2) != net:
        print("* the diff is: %f vs. %f" % (opening_bal - closing_bal, net))
        print(f"* Opening reported at {opening_bal}")
        print(f"* Closing reported at {closing_bal}")
        print(f"* Transactions (net/inflow/outflow): {net} / {inflow} / {outflow}")
        print("* Parsed transactions:")
        for t in sorted(list(transactions), key=lambda t: t.date):
            print(t)
        raise AssertionError("Discrepancy found, bad parse :(. Not all transcations are accounted for, validate your transaction regex.")

def _detect_fi(pdf_text):
    print("Detecting financial institution from pdf...")
    found_fi = None
    for (fi, fi_regexes) in regexes.items():
        if not found_fi and 'fidetect' in fi_regexes:
            match = re.search(fi_regexes['fidetect'], pdf_text, re.IGNORECASE)
            # Check both BMO/BMO_2022 based on startyear regex
            if (match and match.groupdict()['fi']) \
                and (not fi.startswith('BMO') \
                     or (fi.startswith('BMO') and _get_start_year(pdf_text, fi))):
                found_fi = fi
                print(f"Found matching FI: {fi}")
    return found_fi

def _get_account_number(pdf_text, censor=True):
    print("Getting account number...")
    found_accnum = None
    for (accnum_type, accnum_regex) in regexes['COMMON'].items():
        match = re.search(accnum_regex, pdf_text, re.IGNORECASE)
        if (match):
            accnum = match.groupdict()['account_number']
            if (censor):
                if (accnum_type == "accnum_cc"):
                    accnum = "xxxx xxxx xxxx " + accnum[-5:-1] # Keep the last part of the card number (e.g. xxxx xxxx xxxx 7890)
                elif (accnum_type == "accnum_bank"):
                    accnum = "xxxxx-xxx" + accnum[-5:-1] # Keep the last 4 digit of the account number (e.g. xxxxx-xxx7890)
            found_accnum = accnum
            print("Account Number: %s" % accnum)
    return found_accnum

def _get_start_year(pdf_text, fi):
    print("Getting year...")
    match = re.search(regexes[fi]['startyear'], pdf_text, re.IGNORECASE)
    if (match and match.groupdict()['year']):
        year = int(match.groupdict()['year'].replace(', ', ''))
        print("YEAR IS: %d" % year)
        return year


def _get_opening_bal(pdf_text, fi):
    print("Getting opening balance...")
    match = re.search(regexes[fi]['openbal'], pdf_text, re.IGNORECASE)
    print(match)
    if (match and match.groupdict()['cr'] and '-' not in match.groupdict()['balance']):
        balance = float("-" + match.groupdict()['balance'].replace(',', '').replace('$', ''))
        print("Patched credit balance found for opening balance: %f" % balance)
        return balance

    balance = float(match.groupdict()['balance'].replace(',', '').replace('$', ''))
    print("Opening balance: %f" % balance)
    return balance


def _get_closing_bal(pdf_text, fi):
    print("Getting closing balance...")
    match = re.search(regexes[fi]['closingbal'], pdf_text, re.IGNORECASE)
    if (match and match.groupdict()['cr'] and '-' not in match.groupdict()['balance']):
        balance = float("-" + match.groupdict()['balance'].replace(',', '').replace('$', ''))
        print("Patched credit balance found for closing balance: %f" % balance)
        return balance
    
    balance = float(match.groupdict()['balance'].replace(',', '').replace('$', '').replace(' ', ''))
    print("Closing balance: %f" % balance)
    return balance
