import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import os
import sys
import logging
import threading
from dotenv import load_dotenv

from CloverAdapter import InventoryAdapter
from file_check import get_most_recent_file, parse_csv, parse_html, check_qbp_catalog, get_checkpoint

class StdoutRedirector:
    """A class to redirect stdout to a tkinter Text widget."""
    def __init__(self, text_widget):
        self.text_space = text_widget

    def write(self, string):
        self.text_space.insert(tk.END, string)
        self.text_space.see(tk.END)

    def flush(self):
        pass

class OrderInputApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bike Shop Inventory Updater")
        self.root.geometry("1000x600")

        # --- Frame for file paths ---
        path_frame = tk.LabelFrame(root, text="File Paths", padx=10, pady=10)
        path_frame.pack(padx=10, pady=10, fill="x")

        # Order Folder
        tk.Label(path_frame, text="Orders Folder:").grid(row=0, column=0, sticky="w", pady=2)
        self.order_folder_path = tk.StringVar()
        tk.Entry(path_frame, textvariable=self.order_folder_path, width=70).grid(row=0, column=1, padx=5)
        tk.Button(path_frame, text="Browse...", command=self.select_order_folder).grid(row=0, column=2)

        # QBP Catalog File
        tk.Label(path_frame, text="QBP Catalog File:").grid(row=1, column=0, sticky="w", pady=2)
        self.qbp_catalog_path = tk.StringVar()
        tk.Entry(path_frame, textvariable=self.qbp_catalog_path, width=70).grid(row=1, column=1, padx=5)
        tk.Button(path_frame, text="Browse...", command=self.select_qbp_catalog).grid(row=1, column=2)

        # .env File
        tk.Label(path_frame, text=".env File:").grid(row=2, column=0, sticky="w", pady=2)
        self.env_path = tk.StringVar()
        tk.Entry(path_frame, textvariable=self.env_path, width=70).grid(row=2, column=1, padx=5)
        tk.Button(path_frame, text="Browse...", command=self.select_env_file).grid(row=2, column=2)

        # --- Frame for controls and output ---
        control_frame = tk.Frame(root, padx=10, pady=10)
        control_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Run Button
        self.run_button = tk.Button(control_frame, text="Run Inventory Update", command=self.start_processing_thread, bg="lightblue")
        self.run_button.pack(pady=5)

        # Output Console
        output_frame = tk.LabelFrame(control_frame, text="Output", padx=5, pady=5)
        output_frame.pack(fill="both", expand=True)
        self.output_console = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=20)
        self.output_console.pack(fill="both", expand=True)

        # Redirect stdout
        sys.stdout = StdoutRedirector(self.output_console)
        sys.stderr = StdoutRedirector(self.output_console)

    def select_order_folder(self):
        path = filedialog.askdirectory(title="Select Orders Folder")
        if path:
            self.order_folder_path.set(path)

    def select_qbp_catalog(self):
        path = filedialog.askopenfilename(title="Select qbpcatalog.txt", filetypes=[("Text files", "*.txt")])
        if path:
            self.qbp_catalog_path.set(path)

    def select_env_file(self):
        path = filedialog.askopenfilename(title="Select .env file", filetypes=[("ENV files", ".env"), ("All files", "*.*")])
        if path:
            self.env_path.set(path)

    def start_processing_thread(self):
        folder_path = self.order_folder_path.get()
        qbp_path = self.qbp_catalog_path.get()
        env_path = self.env_path.get()

        if not all([folder_path, qbp_path, env_path]):
            messagebox.showerror("Error", "All file paths must be selected before running.")
            return

        self.run_button.config(state=tk.DISABLED, text="Processing...")
        
        # Run the processing in a separate thread to keep the GUI responsive
        processing_thread = threading.Thread(
            target=self.process_order, 
            args=(folder_path, qbp_path, env_path),
            daemon=True
        )
        processing_thread.start()

    def process_order(self, folder_path, qbp_catalog_path, env_path):
        """This method contains the core logic from input_order.py"""
        try:
            # --- Setup ---
            load_dotenv(dotenv_path=env_path)
            token = os.getenv("TOKEN")
            mid = os.getenv("CLIENT_ID")
            base_url = "https://api.clover.com/v3/merchants"

            if not token or not mid:
                print("Error: TOKEN or CLIENT_ID not found in .env file.\n")
                return

            # --- Logging ---
            log_file_path = os.path.join(folder_path, 'inv_writes.log')
            logger = logging.getLogger(__name__)
            logging.basicConfig(filename=log_file_path, 
                                encoding='utf-8', 
                                format="%(asctime)s [%(levelname)s] %(message)s",
                                level=logging.INFO,
                                force=True) # force=True to reconfigure on subsequent runs
            
            def log_exception(exc_type, exc_value, exc_traceback):
                if issubclass(exc_type, KeyboardInterrupt):
                    sys.__excepthook__(exc_type, exc_value, exc_traceback)
                    return
                logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
                default_excepthook(exc_type, exc_value, exc_traceback)
            
            default_excepthook = sys.excepthook
            sys.excepthook = log_exception

            # --- Main Logic ---
            report_file_path = os.path.join(folder_path, "report.txt")
            order_path = get_most_recent_file(folder_path, report_file_path)
            print(f'Attempting to write {order_path} to inventory\n')

            inv = InventoryAdapter(token, mid, base_url, logger)
            logger.info(f'Starting input of order {order_path}')

            if order_path.endswith(".csv"):
                order = parse_csv(order_path)
            else:
                check_qbp_catalog(qbp_catalog_path)
                inv.add_qbp_inv(qbp_catalog_path)
                order = parse_html(order_path)

            inv.print_table_header()

            checkpoint_code = get_checkpoint(order_path, report_file_path)
            reached_checkpoint = checkpoint_code is None

            for item in order:
                if not reached_checkpoint and checkpoint_code == item.code:
                    reached_checkpoint = True
                
                if reached_checkpoint:
                    try:
                        if item.code in inv.ids_dict:
                            inv.post_stock(item.code, item.stock)
                        else:
                            inv.post_new_item(item)
                    except Exception as e:
                        print(f"\nERROR processing item {item.code}. Creating checkpoint.\n")
                        with open(report_file_path, "a") as file:
                            file.write(f'{order_path}?{item.code}\n')
                        raise # Re-raise to be caught by the outer try/except and stop processing
            
            with open(report_file_path, "a") as file:
                file.write(order_path + "\n")
            
            print("\nOrder fully uploaded to Clover.")
            logger.info(f'Completed input of order {order_path}')

        except Exception as e:
            print(f"\nAn error occurred: {e}")
            logging.error("Processing failed.", exc_info=True)
        finally:
            # Re-enable the run button on the main thread
            self.root.after(0, self.enable_run_button)

    def enable_run_button(self):
        self.run_button.config(state=tk.NORMAL, text="Run Inventory Update")

if __name__ == "__main__":
    root = tk.Tk()
    app = OrderInputApp(root)
    root.mainloop()
