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

    def _handle_api_error(self, response):
        """
        Helper to raise informative exceptions based on API status codes.
        """
        try:
            content = response.json()
            msg = content.get("message", response.reason)
        except:
            msg = response.text

        if response.status_code == 401:
            raise PermissionError(f"{msg}. Please check your Merchant ID and Token in the .env file.")
        elif response.status_code == 429:
            raise ConnectionError(f"{msg}. Please wait before retrying.")
        else:
            raise Exception(f"Unkown API Error {response.status_code}: {msg}")

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
        
        if 299 >= response.status_code >= 200:
            output = response.json()
            if output['elements'] == []:
                return {}
            for item in output['elements']: 
                if 'code' in item: # if the item has a product code to look up
                    products[item['code']]=item['id']
                    if len(products[item['code']]) != self.id_length:
                        raise Exception(f'CloverID not of length {self.id_length} found.')
            return products
        else:
            self._handle_api_error(response)
    
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
        if 299 >= response.status_code >= 200:
            return response.json()
        else:
            self._handle_api_error(response)

    def _order_table(self, old_stock : int, new_stock : int, get_item_output : dict, new_item : bool) -> dict:
        """
        Writes to logger and returns formatted data from the API calls.
        Args:
            old_stock (int): stock of an item prior to POST request
            new_stock (int): updated stock of an item, returned by the POST request
            get_item_output (dict): item dictionary returned by .get_single_item()
            new_item (bool): indicates whether the item existed prior to the current order input
        Returns: 
            (dict): with important info about the API call
        """
        price = get_item_output.get("price")
        formatted_price = f"${price / 100:.2f}" if price is not None else ""

        output_data = {
            "new": new_item,
            "name": get_item_output.get("name", ""),
            "price": formatted_price,
            "sku": get_item_output.get("sku", ""),
            "old stock": int(old_stock),
            "new stock": int(new_stock),
        }
        
        return output_data

    def post_stock(self, item : OrderItem):
        """
        Updates the stock for an inventory item, 
        This is a separate method because it has a different API endpoint
        Args:
            code: product code or cloverid for the item
            quantity: the new stock count for the item, make sure to add old stock
        """
        # update stock
        url = f'{self.url}/item_stocks/{item.cloverid}' 
        headers = {
            "authorization" : "Bearer " + self.token,
            "accept": "application/json",
        }
        payload = {"quantity": item.oldStock + item.newStock}
        post_response = post(url, json=payload, headers=headers)
        if 299 >= post_response.status_code >= 200:
            # log useful data about the order
            self.logger.info(str(item))
        else:
            try:
                msg = post_response.json().get("message", "")
            except:
                msg = post_response.text
            self.logger.error(f'{msg} failed attempting to update stock for item {item.code} ({item.cloverid})')
            self._handle_api_error(post_response)
    
    def post_new_item(self, item : OrderItem):
        """
        Adds a new item to the inventory system
        Args:
            item: OrderItem object with the data for the new inventory item
        """
        url = f'{self.url}/items' 
        header = {
            "Authorization" : "Bearer " + self.token,
            "Accept": "application/json",
            "content-type": "application/json"}

        # add new item to inventory
        response = post(url, headers=header, json=item.getItemDict())
        if 299 >= response.status_code >= 200:
            output = response.json()
            # add cloverid with set method
            item.updateFromInventory(output)
            # add stock
            self.logger.info(f'Added new item {item.code}')
            return self.post_stock(item)
        else:
            try:
                msg = response.json().get("message", "")
            except:
                msg = response.text
            self.logger.error(f'{msg} failed attempting add new item {item.code} ({item.cloverid})')
            self._handle_api_error(response)
        
    def post_update_item(self, item : OrderItem):
        """
        Updates a current item within the inventory system
        Args:
            item: OrderItem object with the data for the new inventory item
        """
        url = f'{self.url}/items/{item.cloverid}' 
        header = {
            "Authorization" : "Bearer " + self.token,
            "Accept": "application/json",
            "content-type": "application/json"}
        # if item attributes were modified, update them
        if item.modified is True:
            response = post(url, headers=header, json=item.getItemDict())
            if 299 >= response.status_code >= 200:
                self.logger.info(f'Updated attributes for {item.code}')
                return self.post_stock(item)
            else:
                try:
                    msg = response.json().get("message", "")
                except:
                    msg = response.text
                self.logger.error(f'{msg} failed attempting add new item {item.code} ({item.cloverid})')
                self._handle_api_error(response)
        # if not, save an API call and just update the stock
        else:
            return self.post_stock(item)
            