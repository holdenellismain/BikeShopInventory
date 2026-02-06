import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import logging
import threading
from OrderItem import OrderItem
import webbrowser
from dotenv import load_dotenv

# Import your custom modules
# NOTE: These files must be in the same directory as this script
try:
    from CloverAdapter import InventoryAdapter
    from file_check import file_written, get_checkpoint
    from Order import Order
except ImportError as e:
    print(f"Critical Error: Missing required modules. {e}")

class TextHandler(logging.Handler):
    """
    This class allows logging output to be sent to the GUI Text widget
    instead of just the console or a file.
    """
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        # Schedule the update on the main GUI thread
        self.text_widget.after(0, append)

class EditItemWindow(tk.Toplevel):
    """
    A popup window for editing the attributes of an OrderItem.
    """
    def __init__(self, parent, item: OrderItem, item_id, tree, callback):
        super().__init__(parent)
        self.title("Edit Item")
        self.geometry("400x350")
        self.transient(parent)
        self.grab_set()

        self.item = item
        self.item_id = item_id
        self.tree = tree
        self.callback = callback

        self.vars = {}
        
        # Define which fields are editable
        self.editable_fields = ["name", "newStock", "cost", "price", "priceType", "unit"]

        # Create entry widgets for each editable field
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        self.unit_widgets = []

        for i, field in enumerate(self.editable_fields):
            label = tk.Label(frame, text=f"{field.replace('_', ' ').title()}:")
            label.grid(row=i, column=0, sticky="w", pady=2)
            
            current_value = getattr(self.item, field)
            # Format currency fields
            if field in ['cost', 'price'] and current_value is not None:
                current_value = f"${current_value / 100:.2f}"

            var = tk.StringVar(value=current_value if current_value is not None else "")
            self.vars[field] = var
            
            widget = None

            if field == "priceType":
                price_type_options = ["FIXED", "PER_UNIT", "VARIABLE"]
                if var.get() not in price_type_options:
                    var.set(price_type_options[0]) # Default to FIXED
                
                var.trace_add("write", self.toggle_unit_visibility)

                widget = ttk.OptionMenu(frame, var, var.get(), *price_type_options)
                widget.grid(row=i, column=1, sticky="ew", pady=2)
            else:
                widget = tk.Entry(frame, textvariable=var, width=40)
                widget.grid(row=i, column=1, sticky="ew", pady=2)
            
            if field == "unit":
                self.unit_widgets = [label, widget]
 
        frame.grid_columnconfigure(1, weight=1)
        
        self.toggle_unit_visibility()

        # Save and Cancel buttons
        btn_frame = tk.Frame(self, pady=10)
        btn_frame.pack(fill="x")
        
        save_btn = tk.Button(btn_frame, text="Save", command=self.save_changes)
        save_btn.pack(side="right", padx=10)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right")

    def toggle_unit_visibility(self, *args):
        """Shows or hides the unit field based on priceType."""
        if self.vars["priceType"].get() == "PER_UNIT":
            for w in self.unit_widgets:
                w.grid()
        else:
            for w in self.unit_widgets:
                w.grid_remove()

    def save_changes(self):
        """
        Collects data from entries, updates the OrderItem, and refreshes the Treeview.
        """
        new_data = {field: var.get() for field, var in self.vars.items()}
        self.callback(self.item, new_data) # Use callback to update item and tree
        self.destroy()


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bike Shop Inventory Manager")
        self.root.geometry("900x700") # Made wider for the table

        # Variables to store paths
        self.order_path_var = tk.StringVar()
        self.catalog_path_var = tk.StringVar()
        self.env_path_var = tk.StringVar()
        self.report_path_var = tk.StringVar()

        self.order = None
        self.inv = None 

        # get base directory
        base_dir = os.getcwd() # if running a script
        if getattr(sys, 'frozen', False): #if compiled by PyInstaller on Mac
            base_dir = os.path.dirname(sys.executable)

        # Default paths for .env and report.txt
        # for the env it may be either "env" (mac) or ".env" (windows)
        env_name = "env" if os.path.exists(os.path.join(base_dir, "env")) else ".env"
        self.env_path_var.set(os.path.join(base_dir, env_name))
        self.report_path_var.set(os.path.join(base_dir, "report.txt"))

        self.create_widgets()

    def create_widgets(self):
        # --- File Selection Section ---
        self.input_frame = tk.LabelFrame(self.root, text="Configuration", padx=10, pady=10)
        self.input_frame.pack(fill="x", padx=10, pady=5)

        # Order File
        self.create_file_row(self.input_frame, "Order File (.csv or .html):", self.order_path_var, 0)
        
        # .env File
        self.create_file_row(self.input_frame, ".env File:", self.env_path_var, 1)

        # Report File
        self.create_file_row(self.input_frame, "Report History File:", self.report_path_var, 2)

        # QBP Catalog
        self.create_file_row(self.input_frame, "QBP Catalog (.txt):", self.catalog_path_var, 3)

        # --- Action Section ---
        action_frame = tk.Frame(self.root, padx=10, pady=10)
        action_frame.pack(fill="x")

        self.run_btn = tk.Button(action_frame, text="Load Order",
                                 command=self.start_load_order_thread, 
                                 bg="#B6FB6F", #windows
                                 highlightbackground="#B6FB6F") #macos
        self.run_btn.pack(fill="x", pady=5)

        # --- Output Section (Tabs) ---
        # Using a Notebook to switch between Log and Table view
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab 1: Table
        table_tab = tk.Frame(self.notebook)
        self.notebook.add(table_tab, text="Item Preview")

        self.create_table_widget(table_tab)

        # Tab 2: Log
        log_tab = tk.Frame(self.notebook)
        self.notebook.add(log_tab, text="Process Log")
        
        self.log_area = scrolledtext.ScrolledText(log_tab, state='disabled', height=15)
        self.log_area.pack(fill="both", expand=True)

        # Setup Logging
        self.setup_logging()

    def create_table_widget(self, parent):
        # Get table definition from OrderItem
        table_def = OrderItem.get_treeview_definition()
        columns = table_def["columns"]

        self.tree = ttk.Treeview(parent, columns=columns, show="headings")

        # Configure a tag for highlighting rows with low margin
        self.tree.tag_configure('highlight', background='yellow')
        self.tree.tag_configure('odd', background='#F0F0F0')
        self.tree.tag_configure('even', background='white')

        # Setup Headings
        for col, heading in table_def["headings"].items():
            self.tree.heading(col, text=heading)

        # Setup Column Widths
        for col, width in table_def["column_widths"].items():
            self.tree.column(col, width=width)

                # Scrollbars
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout for tree and scrollbars
        self.tree.grid(column=0, row=0, sticky='nsew')
        vsb.grid(column=1, row=0, sticky='ns')
        hsb.grid(column=0, row=1, sticky='ew')

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # Bind double-click event
        self.tree.bind("<Double-1>", self.on_item_double_click)

    def create_file_row(self, parent, label_text, variable, row):
        """Helper to create a Label, Entry, and Browse button row"""
        file_types = None
        if "Order File" in label_text:
            file_types = [("Order Files", "*.csv *.html"), ("All files", "*.*")]
        elif "Catalog" in label_text:
            file_types = [("Text files", "*.txt"), ("All files", "*.*")]
        elif ".env" in label_text:
            file_types = [("Environment files", "*.env"), ("All files", "*.*")]
        elif "Report" in label_text:
            file_types = [("Text files", "*.txt"), ("All files", "*.*")]

        tk.Label(parent, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(parent, textvariable=variable, width=50).grid(row=row, column=1, padx=5, pady=5)
        tk.Button(parent, text="Browse", command=lambda: self.browse_file(variable, file_types)).grid(row=row, column=2, padx=5, pady=5)

    def browse_file(self, variable, filetypes=None):
        """Opens a file dialog to select a file."""
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            variable.set(filename)

    def setup_logging(self):
        # Create logger
        self.logger = logging.getLogger("InventoryApp")
        self.logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        # 1. File Handler (Original logic)
        file_handler = logging.FileHandler('inv_writes.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 2. GUI Text Handler (New logic)
        text_handler = TextHandler(self.log_area)
        text_handler.setFormatter(formatter)
        self.logger.addHandler(text_handler)

    def set_input_frame_state(self, state):
        """Enables or disables all widgets in the input frame."""
        for child in self.input_frame.winfo_children():
            child.configure(state=state)

    def start_load_order_thread(self):
        """Runs the process in a separate thread to keep GUI responsive"""
        self.run_btn.config(state="disabled", text="Processing...")
        self.set_input_frame_state("disabled")
        # Clear previous table entries
        for item in self.tree.get_children():
            self.tree.delete(item)

        thread = threading.Thread(target=self.run_process)
        thread.daemon = True
        thread.start()

    def on_item_double_click(self, event):
        """Handles the double-click event of the treeview to open the editor."""
        item_id = self.tree.focus() # Get selected item
        if not item_id:
            return

        # The iid of the tree item is its index in the self.order.items list
        item_index = self.tree.index(item_id)
        order_item_to_edit = self.order.items[item_index]

        EditItemWindow(self.root, order_item_to_edit, item_id, self.tree, self.update_item_and_refresh_row)

    def update_item_and_refresh_row(self, item, new_data):
        """Callback to update the item and refresh its row in the tree."""
        try:
            item.updateAttributes(new_data)
            # Find the treeview item by finding the object in our list
            item_index = self.order.items.index(item)
            item_id = self.tree.get_children()[item_index] # This is the iid

            # Highlight the row if price is too low
            tags = ['even' if item_index % 2 == 0 else 'odd']
            if item.price_warning() is True:
                    tags.append('highlight')

            # Update the item in the treeview with new values and tags
            self.tree.item(item_id, values=item.get_treeview_values(), tags=tuple(tags))
        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to update item: {e}")

    def start_commit_inventory_thread(self):
        """Runs the inventory commit process in a separate thread."""
        self.run_btn.config(state="disabled", text="Committing to Clover...")
        thread = threading.Thread(target=self.commit_inventory_to_clover)
        thread.daemon = True
        thread.start()

    def commit_inventory_to_clover(self):
        """Posts new items and updates stock in Clover inventory."""
        try:
            order_path = self.order_path_var.get()
            report_path = self.report_path_var.get()

            # This logic is adapted from your input_order.py script
            checkpoint_code = get_checkpoint(order_path, report_path)
            reached_checkpoint = checkpoint_code is None

            for item in self.order.items:
                if not reached_checkpoint and checkpoint_code == item.code:
                    reached_checkpoint = True

                if reached_checkpoint:
                    try:
                        if item.newItem:
                            self.inv.post_new_item(item)
                        else:
                            self.inv.post_update_item(item)
                    except Exception as e:
                        self.logger.error(f"Failed on item {item.code}. Creating checkpoint.", exc_info=True)
                        with open(report_path, "a") as file:
                            file.write(f'{order_path}?{item.code}\n')
                        raise e # Re-raise to stop processing and show error

            # Mark order as fully processed
            with open(report_path, "a") as file:
                file.write(order_path + "\n")
            self.logger.info(f"Order fully uploaded to Clover: {order_path}")
            self.root.after(0,lambda: messagebox.showinfo("Success",
                    "Order has been successfully committed to Clover inventory."))
            self.root.after(0,lambda: self.run_btn.config(state="normal",text="Exit",command=self.root.destroy))

        except Exception as e:
            self.logger.error(f"An error occurred during inventory commit: {e}", exc_info=True)
            self.root.after(0,lambda: messagebox.showerror("Commit Error",
                    f"Failed to commit inventory: {e}"))
            self.root.after(0,lambda: self.run_btn.config(state="normal",text="Add to Clover Inventory"))

    def run_process(self):
        try:
            # 1. Get Inputs
            order_path = self.order_path_var.get()
            qbp_path = self.catalog_path_var.get()
            env_path = self.env_path_var.get()
            report_path = self.report_path_var.get()

            # 2. Validation
            if not all([order_path, env_path, report_path]):
                raise ValueError("Order, .env, and Report file paths must be selected.")

            is_qbp_order = order_path.lower().endswith(".html")
            if not (order_path.lower().endswith(".csv") or is_qbp_order):
                raise ValueError("Order file must be a .csv or .html file.")
            
            if is_qbp_order and not qbp_path:
                raise ValueError("QBP Catalog file is required for .html orders.")
            
            if is_qbp_order:
                if not messagebox.askyesno("Confirmation", "Has the QBP Inventory file been updated?"):
                    webbrowser.open("https://login.qbp.com/login")
                    raise ValueError("Please update the QBP Catalog file.")
            
            if not os.path.exists(order_path): raise FileNotFoundError(f"Order file not found: {order_path}")
            if is_qbp_order and not os.path.exists(qbp_path): raise FileNotFoundError(f"Catalog file not found: {qbp_path}")
            if not os.path.exists(env_path): raise FileNotFoundError(f"Env file not found: {env_path}")

            # 3. Check if file written (Using report filename from path)
            if file_written(order_path, report_path):
                raise ValueError(f"Order file '{os.path.basename(order_path)}' has already been processed according to {os.path.basename(report_path)}.")

            # 4. Load Env
            load_dotenv(dotenv_path=env_path)
            token = os.getenv("TOKEN")
            mid = os.getenv("CLIENT_ID")
            base_url = "https://api.clover.com/v3/merchants"

            if not token or not mid:
                raise ValueError("TOKEN or CLIENT_ID missing from .env file")

            self.logger.info(f'Starting input of order {order_path}')

            # 5. Initialize API
            self.inv = InventoryAdapter(token, mid, base_url, self.logger)

            # 6. Load Order
            self.order = Order(order_path, qbp_path, self.logger)
            for item in self.order.items:
                # Update Inventory Logic
                if item.code in self.inv.ids_dict:
                    itemData = self.inv.get_single_item(item.code)
                    item.updateFromInventory(itemData)
            
            # 7. Update GUI Table
            # Use root.after to ensure UI updates happen on the main thread
            for i, item in enumerate(self.order.items):
                if hasattr(item, 'get_treeview_values'):
                    # Determine if the row should be highlighted
                    tags = ['even' if i % 2 == 0 else 'odd']
                    if item.price_warning() is True:
                            tags.append('highlight')

                    values = item.get_treeview_values()
                    # The iid is set to the index to easily map back
                    self.root.after(0, lambda item_index=i, item_values=values, item_tags=tuple(tags): 
                                   self.tree.insert("", "end", iid=item_index, values=item_values, tags=item_tags))
            
            self.notebook.select(0) # Switch to the Table tab
            self.logger.info(f"Successfully loaded items.")

            # On success, change button to commit inventory
            # this runs self.start_commit_inventory_to_clover
            self.root.after(0, lambda: self.run_btn.config(state="normal", text="Add to Clover Inventory", command=self.start_commit_inventory_thread))

        except Exception as e:
            self.logger.error(f"Error: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            # On failure, reset the button to its original state
            self.root.after(0, lambda: self.run_btn.config(state="normal", text="Load Order", command=self.start_load_order_thread))
            self.root.after(0, lambda: self.set_input_frame_state("normal"))
        
if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()
