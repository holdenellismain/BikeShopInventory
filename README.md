# Bike Shop Inventory Management

## Goals
- Create an app to automate order input through Clover's REST API
- Make the code easy to debug and update for future mechanics.
- Make the app as easy to use as possible.

## Context
The bike shop I work at uses the [Clover](https://www.clover.com/) inventory and sales management system. Every year, we count our physical inventory and compare it to what Clover thinks we have in stock. Usually there is a large disparity and because our inventory is over 3500 items, this correction requires a lot of manual labor. In order to reduce this workload from upstream, I wanted to improve our process of inputting new orders (previously done manually by mutliple different employees with [7Spaces](https://www.7-spaces.com/stock/login)) to improve accuracy and consistency as well as saving valuable time.

## Steps
1. Parse files
     - We recieve inventory from two different suppliers, [JBI](https://jbi.bike/site/) and [QBP](https://www.qbp.com/). Orders come in different types and parsing is handled by [Order.py](Order.py)
     - Certain data is missing from the order form itself, which is handled by [qbiqbp_scrape.py](jbiqbp_scrape.py). For JBI, it is scraped from their website but for QBP is has to be drawn from a catalog tsv file.
     - Items are loaded into `OrderItem` objects
2. Input to inventory
   - Use the API to input items one-by-one. This functionality is handled by the `InventoryAdapter` class in [CloverAdapter.py](CloverAdapter.py)
   - A log file is used to keep track of actions

There is a little more complexity in terms of mechanic workflow and error handling. This is integrated into the GUI through [gui.py](gui.py)

## File Structure

* [gui.py](gui.py) is the central hub.
* [CloverAdapter.py](gui.py) helps users connect with Clover's Inventory API through the class `InventoryAdapter`.
* [OrderItem.py](OrderItem.py) class to help store data for clover items in Python program (abstraction).
* [CloverOrderReaderAdapter.py](CloverOrderReaderAdapter.py) is an extension for `InventoryAdapter` that allows some functionality to read orders. 
* [Order.py](Order.py) helps initialize an order (basically a list but with some extra features).
* [file_check.py](file_check.py) handles some logging features that are essential to order parsing.
* [jbiqbp_scrape.py](jbiqbp_scrape.py) 
* [input_order.py](input_order.py) [DEPRECATED] system for order input that doesn't use a GUI. If the GUI is being difficult, we can use this instead.

## Future Development

- Better updating/compilation procedure into an executable version of [gui.py](gui.py). I've been having to recompile on every time I make any changes using [PyInstaller](https://pyinstaller.org/en/stable/) but I feel like there must be a better way.
- Create unit tests to make it more resilient against changes in order file formatting and the API.
