import os
import glob
from bs4 import BeautifulSoup # needed for parsing QBP order form html
import csv
from OrderItem import OrderItem

def file_written(order_path : str, report_file_path : str) -> bool:
    '''
    Checks if an order file has been written to the inventory previously
    Args:
        order_path (str): the path for the order file, either .csv or .html
        report_file_path (str): the path to this program's report file
    Returns:
        (bool): indicates if the file has been written
    ''' 
    with open(report_file_path, "r") as file:
        paths = file.readlines()
        for path in paths:
            path = path.strip()
            if path == order_path.strip():
                return True
    # if no line in report.txt matches order_path:
    return False

def get_checkpoint(order_path : str, report_file_path : str) -> str | None:
    '''
    Gets the checkpoint for a given file path
    Args:
        order_path (str): the path for the order file, either .csv or .html
        report_file_path (str): the path to this program's report file
    Returns:
        (str): the item code corresponding to the checkpoint or None if the order has not been written before
    '''  
    
    with open(report_file_path, "r") as file:
        for line in file:
            line = line.strip()
            if not line or "?" not in line:
                continue
            path, item_code = line.split("?", 1)
            if path == order_path:
                return item_code
    return None

def get_most_recent_file(directory : str, report_file_path : str) -> str:
    '''
    Gets the most recent order file path from a folder containing orders.
    Args:
        directory (str): folder path containing JBI and QBP order files
        report_file_path (str): the path to this program's report file
    Returns:
        most_recent_file (str): file path to the most recently downloaded order
    Raises: 
        Exception: if the folder does not contain .csv or .html files
    '''
    # Define file patterns for CSV and HTML
    file_extensions = ["*.csv", "*.html"]
    
    # Get a list of all matching files
    files = []
    for pattern in file_extensions:
        files.extend(glob.glob(os.path.join(directory, pattern)))
    
    # If no files found, return None
    if not files:
        raise Exception("No files in the select folder. Likely incorrect path.")
    
    # if the report.txt file does not yet exist, create a blank one
    if not os.path.exists(report_file_path):
        with open(report_file_path, "w") as file:
            pass

    # Remove files that have already been written
    i = 0
    while i < len(files):
        if file_written(files[i], report_file_path):
            files.pop(i)
        else:
            i += 1
    
    #if all fils have already been written (all files removed from list by prev statement)
    if files == []:
        raise Exception("All orders written to inventory")
    
    # Get the most recently created file
    most_recent_file = max(files, key=os.path.getctime)
    return most_recent_file
            
def parse_html(html_path : str) -> list:
    '''
    Gets order information from QBP html file
    Args:
        order_path (str): the path for the .html order file
    Returns:
        order: list of OrderItems representing each item in the order
    ''' 
    # load in order html
    with open(html_path, 'r', encoding='utf-8') as htmlfile:
        content = htmlfile.read()
        soup = BeautifulSoup(content, features="lxml")
    
        order = [] # initalize empty order
        # find order tables within the file
        table = soup.find("table") # find highest level table
        sub_tables = table.select("table")
        for table in sub_tables:
            rows = table.select("tr")
            length = len(rows[0].select("th"))
            if length == 8: # exclude order information tables
                for row in rows:
                    cols = row.select("td") 
                    if len(cols) == 8: # exclude headers/footers, for some reason each row has a blank column at the end
                        order.append(OrderItem([col.text.strip() for col in cols]))
        return order

def check_csv(file_path) -> bool:
    '''
    Checks if the csv file matches the expected format for a JBI order
    Args:
        file_path (str): the path for the order file .csv
    Returns:
        indicates if the file is formatted as expected
    '''
    expected_header = [
    "JBI Order No", "Location", "Part Number", "Description", "Qty Ordered", 
    "Qty Allocated", "Qty Invoiced", "Qty Canceled", "Qty BO", "Unit Price", 
    "Brand", "UPC/EAN", "MAP", "MSRP"]
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # Read the first row
        # Strip whitespace from each header field
        header = [h.strip() for h in header]
        return header == expected_header

def parse_csv(csv_path : str) -> list:
    '''
    Gets order information from QBP html file
    Args:
        order_path (str): the path for the .html order file
    Returns:
        order: list of OrderItems representing each item in the order
    ''' 
    assert check_csv(csv_path), "Incorrect order csv formatting"

    order = [] # initialize empty order

    # load in order csv
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        reader.fieldnames = [name.strip() for name in reader.fieldnames] # cleans header names, sometimes have weird spacing
        for row_dict in reader:
            order.append(OrderItem(row_dict))
    return order

def check_qbp_catalog(file_path):
    """
    Verifies that QBP catalog is recent
    """
    # TODO
    # check that it exists
    # check that it was created in the last week
    # if either of these is false, tell the user to download a new one and put it in the orders folder
    pass