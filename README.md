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

There is a little more complexity in terms of workflow and error handling. This is integrated into the GUI through [gui.py](gui.py)

## Future Development

- Turn the GUI into a single executable instead of a `.py` file
- Created a dedicated documentation file/usage guide.
- Create unit tests to make it more resilient against changes in order file formatting and the API.
