from requests import get
import warnings
from CloverAdapter import InventoryAdapter as BaseInventoryAdapter
from OrderItem import OrderItem
import logging

# --- Experimental Feature ---
# This file provides an experimental extension to the main InventoryAdapter.
# It adds functionality for reading order data, which is not yet considered stable.
# It inherits from the stable BaseInventoryAdapter and should be used with caution.

class ExperimentalWarning(UserWarning):
    """Custom warning for using experimental features."""
    pass

class InventoryAdapter(BaseInventoryAdapter):
    """
    Extends the base InventoryAdapter with experimental features for reading order data.

    .. warning::
       This class contains experimental functionality that is subject to change or
       removal in future versions without notice. It is not recommended for
       production use.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "You are using an InventoryAdapter with experimental order-reading features. "
            "This functionality is unstable and may change.",
            ExperimentalWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)

    def read_date_range_orders(self, start_timestamp_ms: int, end_timestamp_ms: int):

        """
        (EXPERIMENTAL) Gets all inventory items sold from orders within a specific date range.

        This method queries for orders created within the given timeframe,
        expands the line items for each order, and abstracts them into OrderItem objects.
        It handles API pagination internally to retrieve all orders in the range.

        Note: The 'newStock' attribute in the returned OrderItem objects represents
        the quantity of items sold (a negative change to inventory).

        Args:
            start_timestamp_ms (int): The start of the date range as a Unix timestamp in milliseconds.
            end_timestamp_ms (int): The end of the date range as a Unix timestamp in milliseconds.

        Returns:
            list[OrderItem]: A list of OrderItem objects, with newStock representing the amount sold.
        """
        items = []
        offset = 0
        total_orders_processed = 0

        headers = {
            "authorization": "Bearer " + self.token,
            "accept": "application/json",
        }
    
        filters = [
            f"createdTime>={start_timestamp_ms}",
            f"createdTime<={end_timestamp_ms}"
        ]

        limit = 1000  # Max limit per Clover API docs
        
        while True:
            if self.logger:
                self.logger.info(f"Fetching orders with offset {offset}...")

            params = {
                'filter': filters,
                'expand': 'lineItems',
                'limit': limit,
                'offset': offset
            }
            
            response = get(f'{self.url}/orders', headers=headers, params=params)
            
            if not (200 <= response.status_code < 300):
                self._handle_api_error(response)

            data = response.json()
            orders = data.get('elements', [])

            if not orders:
                break  # no more orders, exit loop
            total_orders_processed += len(orders)

            for order in orders:
                if 'lineItems' not in order or 'elements' not in order.get('lineItems', {}):
                    continue

                for line_item in order['lineItems']['elements']:
                    item_ref = line_item.get('item')
                    # handles edge case where an order has custom items not in the inventory on it
                    if not item_ref or 'id' not in item_ref:
                        if self.logger:
                            self.logger.debug(f"Skipping line item without an inventory item reference in order {order.get('id')}.")
                        continue

                    # unitQty is in thousandths of a unit (e.g., 1000 = 1 unit).
                    # Default to 1 unit if not present.
                    # This handles items sold by weight/length (e.g., 1.5 units is a unitQty of 1500).
                    quantity = line_item.get('unitQty', 1000) / 1000.0

                    kwargs = {
                        'cloverid': item_ref['id'],
                        'name': line_item.get('name'),
                        'code': line_item.get('itemCode'),
                        'newStock': quantity  # This represents quantity sold and can be a float.
                    }
                    
                    try:
                        # Using manual init of OrderItem. For better type safety and clarity,
                        # TODO: consider adding a dedicated class method to OrderItem like
                        # `OrderItem.from_clover_line_item(line_item)` in the future.
                        order_item = OrderItem(**kwargs)
                        items.append(order_item)
                    except ValueError as e:
                        if self.logger:
                            self.logger.warning(f"Could not create OrderItem for line item {line_item.get('id')}: {e}")

            offset += limit

        if self.logger:
            self.logger.info(f"Finished fetching. Found {len(items)} line items across {total_orders_processed} orders.")
        return items