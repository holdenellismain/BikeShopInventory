import csv
from OrderItem import OrderItem
from bs4 import BeautifulSoup # needed for parsing QBP order form html

class Order:
    """
    Represents an order from either a JBI (.csv) or QBP (.html) file,
    containing a list of OrderItem objects.
    """
    def __init__(self, order_path: str, qbp_catalog_path: str = None, logger=None):
        """
        Initializes an Order object by parsing the given order file.

        Args:
            order_path (str): The file path to the order file (.csv or .html).
            qbp_catalog_path (str, optional): Path to the QBP catalog file.
                                              Required for QBP (.html) orders.
            logger (logging.Logger, optional): Logger for logging messages.
        """
        self.order_path: str = order_path
        self.is_qbp_order: bool = order_path.endswith(".html")
        self.items = []
        self.logger = logger

        if self.is_qbp_order:
            if not qbp_catalog_path:
                raise ValueError("qbp_catalog_path is required for QBP (HTML) orders.")
            qbp_inv = self._load_qbp_inv(qbp_catalog_path)
            self.items = self.parse_html(self.order_path)
            for item in self.items:
                try:
                    item.updateFromCatalog(qbp_inv)
                except KeyError as ke:
                    raise ValueError(f"'{item.code}' not in QBP Catalog. Try downloading a new version.")
        else:
            self.items = self.parse_csv(self.order_path)

    def parse_html(self, html_path : str) -> list:
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

    def check_csv(self, file_path) -> bool:
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

    def parse_csv(self, csv_path : str) -> list:
        '''
        Gets order information from QBP html file
        Args:
            order_path (str): the path for the .html order file
        Returns:
            order: list of OrderItems representing each item in the order
        ''' 
        assert self.check_csv(csv_path), "Incorrect order csv formatting"

        order = [] # initialize empty order

        # load in order csv
        with open(csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            reader.fieldnames = [name.strip() for name in reader.fieldnames] # cleans header names, sometimes have weird spacing
            for row_dict in reader:
                order.append(OrderItem(row_dict))
        return order

    def _load_qbp_inv(self, path: str) -> dict:
        """
        Loads the QBP inventory from file so that SKU/UPC codes can be added.
        Args:
            path (str): the file path to qbpcatalog.txt
        Returns:
            dict
        """
        qbp_inventory = {}
        with open(path, encoding="windows-1252", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                qbp_inventory[row["ProdId"]] = {
                    "UPC": row["UPC"],
                    "MSRP": row["MSRP"],
                    "MAP": row["MAP"],
                }
        return qbp_inventory

    def __iter__(self):
        """Allows iterating directly over the items in the order."""
        return iter(self.items)