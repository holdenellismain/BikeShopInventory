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
            self.price = None # updates from QBP catalog in post_new_item() if it is a new item
            self.stock = int(order_row[4])
            self.upc = None # updates from QBP catalog in post_new_item() if it is a new item
            self.fromQBP = True # flag to improve readability
        elif isinstance(order_row, dict):
            # Extracted from JBI order csv
            self.name = order_row["Description"].upper()
            self.code = order_row["Part Number"]
            self.cost = int(float(order_row["Unit Price"])*100)
            # set price as MAP if it is > 0, otherwise use whichever is less out of MSRP and cost * 2
            MAP = int(float(order_row["MAP"])*100) # temp variables to improve readability, not object attributes
            MSRP = int(float(order_row["MSRP"])*100)
            # self.price = MAP if MAP > 0 else min(self.cost * 2, MSRP)
            self.price = self.cost * 2
            self.stock = int(order_row["Qty Invoiced"])
            self.upc = order_row["UPC/EAN"]
            self.fromQBP = False
        else:
            raise TypeError("Unsupported format for item creation")

    def updateItem(self, qbp_inv : dict):
        """
        Updates the UPC/SKU for an order item 
        Args:
            qpb_inv (dict): uses product code as the key, value is dictionary with UPC, MSRP, and MAP
        """
        MAP = int(float(qbp_inv[self.code]["MAP"])*100)
        MSRP = int(float(qbp_inv[self.code]["MSRP"])*100)
        #self.price = MAP if MAP > 0 else min(self.cost * 2, MSRP)
        self.price = self.cost * 2
        self.upc = qbp_inv[self.code]["UPC"]

    def getItemDict(self) -> dict:
        """
        Returns a data dictionary so that the item can be added to inventory via the API
        """
        return {
            "isRevenue": True,
            "name" : self.name,
            "code" : self.code,
            "sku" : self.upc,
            "price" : self.price,
            "cost" : self.cost,
        }

    def __str__(self):
        # Overrides print method
        return f"{self.name} ({self.code}) has {self.stock} units bought for ${self.cost / 100}"