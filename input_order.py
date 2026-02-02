from CloverAdapter import InventoryAdapter
from dotenv import load_dotenv
import os
from file_check import file_written, get_checkpoint
import logging
from Order import Order
import sys

default_excepthook = sys.excepthook # save default error hook, console

def log_exception(exc_type, exc_value, exc_traceback):
    # Skip KeyboardInterrupt to allow Ctrl+C without stacktrace
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Log to file
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    # show the exception in console
    default_excepthook(exc_type, exc_value, exc_traceback)

if __name__ == "__main__":
    # replace this with the path to the folder containing all new orders
    order_path = "C:/Users/fires/Downloads/orders/JBI_Order_6805843.csv"
    assert file_written(order_path, "report.txt") == False, "File already written to inventory"

    # replace this with the path for the most recent catalog downloaded from 
    # qpb.com/qbponlinestorefront/services/product_database
    qbp_catalog_path = "C:/Users/fires/Downloads/orders/qbpcatalog.txt"

    env_path = "C:/Users/fires/Python Projects/Bike Shop Inventory/.env" # API key stored here
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("TOKEN")
    mid = os.getenv("CLIENT_ID")
    base_url = "https://api.clover.com/v3/merchants"

    # set up logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='inv_writes.log', 
                        encoding='utf-8', 
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        level=logging.INFO)
    sys.excepthook = log_exception # set up global exceptions so that they write to log

    # set up API
    inv = InventoryAdapter(token, mid, base_url, logger)
    logger.info(f'Starting input of order {order_path}')

    # Initialize the Order object, which handles parsing the file
    order = Order(order_path, qbp_catalog_path)

    checkpoint_code = get_checkpoint(order_path, "report.txt")
    reached_checkpoint = True if checkpoint_code is None else False # flag
    for item in order:
        # skips all items up until the checkpoint (unless there isn't one) and then tries to write the rest
        if checkpoint_code == item.code:
            reached_checkpoint = True
        if reached_checkpoint:
            try: 
                if item.code in inv.ids_dict:
                    inv.post_update_item(item)
                else:
                    inv.post_new_item(item)
            except:
                # if the program experienced an error on a specific item, 
                # write the order path as well as the item's code in the report file as a checkpoint
                with open("report.txt", "a") as file:
                    file.write(f'{order_path}?{item.code}\n') # uses ? since it isn't allowed in file paths
                raise # allow error to occur anyways so that the program stops and it can be fixed
            
    # update report and log to show that the order has been written
    with open("report.txt", "a") as file:
        file.write(order_path + "\n")
        print("Order fully uploaded to Clover")
        logger.info(f'Completed input of order {order_path}')
