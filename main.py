import tkinter as tk
from gui_model import DiplomaApp

if __name__ == "__main__":
    root = tk.Tk()
    try: 
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception: 
        pass
        
    app = DiplomaApp(root)
    root.mainloop()