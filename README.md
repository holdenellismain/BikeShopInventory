# Bike Shop Inventory Management

## Goals
- Use manual inventory counts in two Google Sheets to update a Clover inventory.
- Get better at working with pandas dataframes in Python
- Handle edge cases and collect some data describing these edge cases so that manual changes can be made.

## Context
The bike shop I work at uses the [Clover](https://www.clover.com/) inventory and sales management system. Every year, we count our physical inventory and compare it to what Clover thinks we have in stock. Usually there is a large disparity and because our inventory is over 3500 items, this correction requires a lot of manual labor. This year, I suggested we use Clover's output to Excel and a Google Sheet to speed up the approach instead of our traditional method of paper checklists. Counting was a slow process so we ended up with items being bought and sold during counting so when I came back to work for the second half of the summer, there were discrepancies in our [original count](Inventory6_12_2024.xlsx) from June. Thus, in August we did a [recount](Inventory8_20_2024.xlsx) of 83 items. 

## Problems
- Some items were only in the recount sheet because we bought them after the original sheet was exported.
- Some items had a correction in both sheets, some items only had it in one.
- Many corrections were something along the lines of "delete" or "remove", which cannot be reimported into Clover.
- Many items are duplicated in the inventory system. This means they have the same product code with two different names of different product codes for the same item.

## Steps
This section is an outline of the algorithm I used in [merge_sheets.py](merge_sheets.py). For the most part, it is an implementation of the two pointer technique that leverages the fact that the recount sheet has all the items from the original count with a few added in between.
1. Sort both sheets by item name. This will be used as a primary key for identifying inventory items.
2. Iterate through the August sheet
   - If the item is not in the June sheet, ignore the June sheet entirely and just write the August correction as the updated quantity in the dataframe.
   - If the item is in the June sheet, write the more recent correction as the updated quantity in the dataframe.
3. Throughout this process the program checks and handles errors such as:
   - A correction that is not numeric, usually indicating that manual action needs to be taken to delete the item from the inventory system.
   - A difference between the change in stock logged by Clover in this two month period and the change logged between our manual counts, if applicable.
4. At the very end of the process:
   - Output a text file with all the items the program has determined should be deleted.
   - Output an Excel file detaling items that have discrepancies in counts
   - Output an Excel file that can be reimported into Clover to update the inventory
     - *Note: the file still needs to have the other sheets addeed to it but these can just be copied directly from the August export*

