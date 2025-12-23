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
    try:
        with open(report_file_path, "r") as file:
            for line in file:
                # Check for full path match, ignoring checkpoint lines
                if line.strip() == order_path.strip():
                    return True
    except FileNotFoundError:
        # If the report file doesn't exist, no orders have been written, 
        # but create a blank one for checkpointing
        with open(report_file_path, "w") as file:
            pass
        return False 
    return False # If the loop completes without finding a match.

def get_checkpoint(order_path : str, report_file_path : str) -> str | None:
    '''
    Gets the checkpoint for a given file path
    Args:
        order_path (str): the path for the order file, either .csv or .html
        report_file_path (str): the path to this program's report file
    Returns:
        (str): the item code corresponding to the checkpoint or None if the order has not been written before
    '''  
    
    try:
        with open(report_file_path, "r") as file:
            for line in file:
                line = line.strip()
                if not line or "?" not in line:
                    continue
                path, item_code = line.split("?", 1)
                if path == order_path:
                    return item_code
    except FileNotFoundError:
        return None # If the report file doesn't exist, there is no checkpoint
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