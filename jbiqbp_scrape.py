from bs4 import BeautifulSoup
import requests

class InvalidCode(Exception):
    pass

class NoUPC(Exception):
    pass

def read_tsv(path : str) -> dict:
    import csv

    inv_dict = {}
    with open(path, 'r') as file:
        tsv_reader = csv.reader(file, delimiter='\t')
        for row in tsv_reader:
            inv_dict[row[0]] = row[1]

    return inv_dict

def JBI_scrape(part_code : str) -> str:
    """
    Scrapes html from
    https://www.jbi.bike/site/product_details.php?part_number={part_code}
    and returns the UPC / EAN number
    Args:
        part_code (str): 5 digit part code used by JBI
    Returns:
        upc (str): the UPC code from JBI
    Raises: 
        Exception: if UPC cannot be found on JBI
    """
    if len(part_code) < 5 or len(part_code) > 6:
        raise InvalidCode("Code should be 5 or 6 digit string")
    
    link = "https://www.jbi.bike/site/product_details.php?part_number="
    response = requests.get(link + part_code)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table_rows = soup.find_all("td") #list of table rows from the webpage
    if table_rows == []:
        raise InvalidCode("JBI search failed")
    for i, row in enumerate(table_rows):
        if row.text == "UPC / EAN": #iterate through until the label for UPC is found
            upc = table_rows[i+1].text #go to the next row and convert to an integer
            return upc
    #if JBI does not have a upc code for the part
    raise NoUPC("The product is on JBI but does not have a SKU/UPC code")

def get_sku(part_code : str, inventory : dict) -> str:
    '''
    Checks QBP inventory sheet and then the JBI website for a part based on the code. 
    If the part has a page, the UPC is returned to be set as the SKU code in Clover.
    Args:
        part_code (str): the part code used by JBI or QBP
        inventory (dict): dictionary of the form {"QBP ID" : "UPC Code"}
    Returns:
        sku (str): the UPC code from either JBI or QBP for the part
    Raises: 
        Exception: if UPC cannot be found on either website
    '''
    try:
        sku = inventory[part_code]
    except:
        #if this fails, an exception will be raised
        sku = JBI_scrape(part_code)
    return sku