from requests import get, post
import csv
from OrderItem import OrderItem
import logging

class InventoryAdapter:
    def __init__(self, token : str, mid : str, base_url : str = "https://api.clover.com/v3/merchants", logger : logging.Logger = None):
        """
        Constructor for InventoryAdapter
        Args:
            token: API Token from Clover
            mid: 13 character alphanumeric merchant ID found through Clover
            base_url (optional): default is https://api.clover.com/v3/merchants, https://apisandbox.dev.clover.com/v3/merchants if using Sandbox
        """
        self.url = f'{base_url}/{mid}'
        self.token = token
        self.logger = logger
        self.id_length = 13 # length for CloverIDs, hard coded
        self.ids_dict = self.get_ids() # {"code" : "CloverID}
        self.qbp_inv = {} # {"code" : "upc"}, should only be populated if working with QBP items
        self.row_format = "{:<10} | {:<25} | {:<12} | {:<14} | {:<10} | {:<10}" # format for print output table

    def add_qbp_inv(self, path : str):
        """
        Loads the QBP inventory from file so that SKU/UPC codes can be added. 
        Updates the self.qbp_inv nested dictionary using the product code as the key
        Args:
            path: file path to qbpcatalog.txt (must be downloaded from QBP)

        """
        with open(path, encoding="windows-1252", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                self.qbp_inv[row["ProdId"]] = {
                    "UPC": row["UPC"],
                    "MSRP": row["MSRP"],
                    "MAP": row["MAP"]
                }

    def get_inv_dict_helper(self, offset = 0):
        """
        Returns a partition of the dictionary used to convert product codes to CloverIDs. 
        Necessary because Clover can only return 1000 items per call
        Args:
            offset (optional) : skip the first n items in the inventory. If no offset is provided, it starts from item 0.
        Returns:
            dict: in the format {'code' : 'CloverID'} for all items
        """
        products = {}

        header = {"Authorization" : "Bearer " + self.token,
                "Accept": "application/json"}
        url = f'{self.url}/items?limit=1000&offset={offset}' 
        response = get(url, headers=header) #http request
        
        output = response.json()
        if 299 >= response.status_code >= 200:
            if output['elements'] == []:
                return {}
            for item in output['elements']: 
                if 'code' in item: # if the item has a product code to look up
                    products[item['code']]=item['id']
                    if len(products[item['code']]) != self.id_length:
                        raise Exception(f'CloverID not of length {self.id_length} found.')
            return products
        else:
            raise Exception(output["message"])
    
    def get_ids(self):
        """
        Returns a dictionary used to convert product codes to CloverIDs. Uses .get_inv_dict_helper method
        Returns:
            dict: in the format {'code' : 'CloverID'} for all items
        """
        # TODO: May be better to write this with yield instead of separate get_inv_dict_helper returns
        # ex: https://www.pretzellogix.net/2021/12/19/step-13-paging-the-endpoints/
        result = self.get_inv_dict_helper()
        all_items = result
        
        offset = 0
        while result != {}:
            offset += 1000
            result = self.get_inv_dict_helper(offset)
            all_items.update(result)
        return all_items

    def get_cloverid(self, code : str):
        """
        Returns a CloverID corresponding to the part code. Includes error handling.
        Args:
            code : part code from JBI or QBP
        Returns:
            str: CloverID for the corresponding inventory item
        """
        try:
            return self.ids_dict[code]
        except: 
            Exception(f'{code} not found in inventory')
    
    def get_single_item(self, code : str):
        """
        Returns data for a single inventory item
        Args:
            code : product code or CloverID for the item
        Returns:
            dict: https://docs.clover.com/dev/reference/inventorygetitem
        """
        if len(code) == 13:
            cloverid = code
        else:
            cloverid = self.get_cloverid(code)
        url = f'{self.url}/items/{cloverid}?expand=itemStock' 

        # get current stock
        headers = {
            "authorization" : "Bearer " + self.token,
            "accept": "application/json",
        }
        response = get(url, headers=headers)
        output = response.json()
        if 299 >= response.status_code >= 200:
            return output
        else:
            raise Exception(output["message"])

    def print_table_header(self):
        """
        Writes to logger and prints header for output table based on row_format defined in constructor.
        """
        print(self.row_format.format("New Item?", "Name", "Sale Price", "SKU Code", "Old Stock", "New Stock"))
        print("-" * 95)
        self.logger.info(["New Item?", "Name", "Sale Price", "SKU Code", "Old Stock", "New Stock"])
        return

    def print_order_table(self, old_stock : int, new_stock : int, get_item_output : dict, new_item : bool):
        """
        Writes to logger and prints an output table to console. Uses row format defined in constructor.
        Args:
            old_stock (int): stock of an item prior to POST request
            new_stock (int): updated stock of an item, returned by the POST request
            get_item_output (dict): item dictionary returned by .get_single_item()
            new_item (bool): indicates whether the item existed prior to 
        """
        # set up row to be written
        row = [
            str(new_item), 
            get_item_output.get("name")[:24], 
            get_item_output.get("price"), 
            get_item_output.get("sku"), 
            int(old_stock), 
            int(new_stock)]
        
        row[2] = f"${row[2] / 100:.2f}" if row[2] is not None else "" # convert price to dollars
        row = [x if x is not None else "" for x in row] # replace None with empty string
        
        # print to console and write to log file
        print(self.row_format.format(*row))
        self.logger.info(row)

    def post_stock(self, code : str, quantity : int):
        """
        Updates the stock for an inventory item
        Args:
            code: product code or cloverid for the item
            quantity: the new stock count for the item, make sure to add old stock
        """
        # convert to a cloverid
        if len(code) == 13:
            cloverid = code
        else:
            cloverid = self.get_cloverid(code)

        # get current stock
        get_output = self.get_single_item(code)
        try:
            current_stock = get_output["itemStock"]["quantity"]
            if get_output['priceType'] != "FIXED": # Usually indicates "PER_UNIT" pricing. Can be "VARIABLE" but we don't use it
                print(f'WARNING: {get_output["name"]} is priced by length. Add new stock manually.')
                self.logger.warning(f'{get_output["name"]} priced by length. No stock added.')
                return
        # for some items (e.g. those created by the first half of post_new_item), 
        # the stock attribute may not exist yet, assume the stock is 0
        except: 
            current_stock = 0

        # update stock
        url = f'{self.url}/item_stocks/{cloverid}' 
        headers = {
            "authorization" : "Bearer " + self.token,
            "accept": "application/json",
        }
        payload = {"quantity": quantity + current_stock}
        post_response = post(url, json=payload, headers=headers)
        post_output = post_response.json()
        if 299 >= post_response.status_code >= 200:
            new_item = True
            if code in self.ids_dict.values() or code in self.ids_dict:
                new_item = False
            self.print_order_table(current_stock, post_output["quantity"], get_output, new_item)
            return
        else:
            self.logger.error(f'{post_output["message"]} failed attempting to update stock for item {code} ({cloverid})')
            raise Exception(post_output["message"])
    
    def post_new_item(self, item : OrderItem):
        """
        Adds a new item to the inventory system
        Args:
            item: OrderItem object with the data for the new inventory item
        """
        if item.fromQBP == True:
            item.updateItem(self.qbp_inv)
        
        url = f'{self.url}/items' 
        header = {"Authorization" : "Bearer " + self.token,
            "Accept": "application/json",
            "content-type": "application/json"}

        # add new item to inventory
        response = post(url, headers=header, json=item.getItemDict())
        output = response.json()
        if 299 >= response.status_code >= 200:
            cloverid = output["id"]
            self.post_stock(cloverid, item.stock)
        else:
            self.logger.error(f'{output["message"]} failed attempting add new item {item.code} ({cloverid})')
            raise Exception(output["message"])
            

