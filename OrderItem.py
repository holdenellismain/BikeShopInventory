class OrderItem:
    def __init__(self, order_row):
        """
        Constructor for OrderItem
        Args:
            order_row: row extracted from a QBP or JBI order output
            JBI: default = True, False indicates that the order is from QBP    
        """
        if isinstance(order_row, list):
            # Extracted from QBP html table
            self.name = order_row[2].upper()
            self.code = order_row[1]
            self.cost = int(float(order_row[5][1:]) * 100) # convert from $1.00 --> 100
            self.price = None # updates from QBP catalog as part of order intialization 
            self.newStock = int(order_row[4])
            self.upc = None # updates from QBP catalog as part of order intialization
            self.fromQBP = True # flag to improve readability
        elif isinstance(order_row, dict):
            # Extracted from JBI order csv
            self.name = order_row["Description"].upper()
            self.code = order_row["Part Number"]
            self.cost = int(float(order_row["Unit Price"])*100)
            # set price as MAP if it is > 0, otherwise use whichever is less out of MSRP and cost * 2
            MAP = int(float(order_row["MAP"])*100) # temp variables to improve readability
            MSRP = int(float(order_row["MSRP"])*100)
            self.price = MAP if MAP > 0 else min(self.cost * 2, MSRP)
            self.newStock = int(order_row["Qty Invoiced"])
            self.upc = order_row["UPC/EAN"]
            self.fromQBP = False
        else:
            raise TypeError("Unsupported format for item creation")
        self.oldStock = 0
        self.priceType = "FIXED"
        self.newItem = True
        self.cloverid = None
        self.modified = False
        self.unit = "Unit Name" # unit for PER_UNIT price type items

    def updateFromCatalog(self, qbp_inv : dict):
        """
        Updates the UPC/SKU for an order item 
        Args:
            qpb_inv (dict): uses product code as the key, value is dictionary with UPC, MSRP, and MAP
        """
        MAP = int(float(qbp_inv[self.code]["MAP"])*100)
        MSRP = int(float(qbp_inv[self.code]["MSRP"])*100)
        self.price = MAP if MAP > 0 else min(self.cost * 2, MSRP)
        self.upc = qbp_inv[self.code]["UPC"]

    def getItemDict(self) -> dict:
        """
        Returns a data dictionary so that the item can be added to inventory via the API
        """
        data = {
            "isRevenue": True,
            "name" : self.name,
            "code" : self.code,
            "sku" : self.upc,
            "price" : self.price,
            "cost" : self.cost,
            "priceType" : self.priceType
        }
        if self.priceType == "PER_UNIT":
            data["unitName"] = self.unit

        return data
    
    def updateFromInventory(self, get_output):
        """
        Uses the API output from get_single_item() to update object attributes
        Args: 
            get_output (dict): https://docs.clover.com/dev/reference/inventorygetitem
        """
        self.name = get_output["name"]
        self.price = get_output["price"]
        self.priceType = get_output["priceType"]
        self.newItem = False
        self.cloverid = get_output["id"]
        try:
            self.oldStock = int(get_output["itemStock"]["quantity"])
        # new items may not have an itemStock attribute yet, so just keep it as 0
        except:
            pass

    def updateAttributes(self, new_data: dict):
        """
        Updates the item's attributes from a dictionary of new data.
        Performs necessary type conversions (e.g., currency strings to cents).
        """
        # lazy flag so that API call to update attributes happens later
        self.modified = True
        
        # don't allow price type changes for existing items. 
        if 'priceType' in new_data and new_data['priceType'] != self.priceType and self.newItem is False:
            raise ValueError("Price Type cannot be changed for existing items. " \
            "Make this change in Clover.")
        for key, value in new_data.items():
            if hasattr(self, key):
                if key == "priceType":
                    assert value in ["FIXED","VARIABLE","PER_UNIT"]
                    setattr(self, key, value)
                elif key == "newStock":
                    try:
                        clean_value = int(value)
                        setattr(self, key, clean_value)
                    except:
                        raise ValueError("New stock count must a whole number")
                # Handle unit conversions
                elif key in ['cost', 'price']:
                    try:
                        # Convert from "$12.34" string to 1234 integer
                        clean_value = str(value).replace('$', '').replace(',', '')
                        setattr(self, key, int(float(clean_value) * 100))
                    except:
                        raise ValueError("Price must be a number")
                elif key in ['name', 'upc', 'unit']:
                    # name and UPC can be set to whatever
                    setattr(self, key, value)
                else: 
                    pass

    def __str__(self):
        # Overrides print method
        return f"Successfully inputted {self.newStock} new units of {self.name} ({self.code}), bought for ${self.cost / 100}"

    # Below are helper functions for generating the Treeview table

    def get_treeview_definition():
        """
        Returns the column definitions (headings and widths) for a Treeview.
        """
        columns = ("New Item", "Name", "Code", "New Stock", "Cost", "Price", "UPC", "Old Stock", "Price Type")
        return {
            "columns": columns,
            "headings": {col: col for col in columns},
            "column_widths": {
                "New Item": 60, "Name": 200, "Code": 100, "New Stock": 60,
                "Cost": 80, "Price": 80, "UPC": 100, "Old Stock": 60, "Price Type": 80
            }
        }

    def get_treeview_values(self) -> tuple:
        """
        Returns a tuple of values formatted for the Treeview.
        """
        # The order must match the get_treeview_definition
        cost_str = f"${self.cost/100:.2f}" if self.cost is not None else "N/A"
        price_str = f"${self.price/100:.2f}" if self.price is not None else "N/A"
        upc_val = self.upc if self.upc is not None else ""
        old_stock_val = self.oldStock if self.oldStock is not None else ""
        price_type_val = self.priceType if self.priceType is not None else ""

        return (self.newItem, self.name, self.code, self.newStock, cost_str, price_str, upc_val, old_stock_val, price_type_val)