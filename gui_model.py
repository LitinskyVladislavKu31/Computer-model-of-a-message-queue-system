import tkinter as tk
from tkinter import ttk, scrolledtext
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random, copy, math
from model import Message, Worker, Broker
from topology_config import TOPOLOGY_CONFIG

class DiplomaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Модель розподіленої черги повідомлень (Диплом)")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        self.inputs = {}
        self.coords = {}
        self.active_lines = []
        self.base_msgs = []
        self.params = None
        self.is_paused = False
        
        self.strats = ["ROUND_ROBIN", "WEIGHTED_ROUND_ROBIN", "LEAST_CONNECTIONS", "WEIGHTED_LEAST_CONNECTIONS", "IP_HASH", "LEAST_RESPONSE_TIME"]
        self.results = {s: 0.0 for s in self.strats}
        self.setup_ui()

    def setup_ui(self):
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=0, minsize=280)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=2)

        ctrl = ttk.LabelFrame(self.root, text="Параметри")
        ctrl.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        for lbl, val in [("Кількість воркерів:", "8"), ("Кількість повідомлень:", "200"), ("Інтенсивність:", "14"), ("Втрата пакетів W_last %:", "0.78")]:
            ttk.Label(ctrl, text=lbl).pack(anchor='w', padx=10, pady=(5, 0))
            e = ttk.Entry(ctrl)
            e.insert(0, val)
            e.pack(fill='x', padx=10)
            self.inputs[lbl] = e
            
            if lbl == "Кількість воркерів:":
                e.bind("<KeyRelease>", self.on_topology_change)

        self.topo_hint_lbl = ttk.Label(ctrl, text="", font=("Arial", 8), wraplength=260, justify="left")
        self.topo_hint_lbl.pack(anchor='w', padx=10, pady=(3, 0))

        ttk.Separator(ctrl).pack(fill='x', pady=10, padx=10)
        
        self.q_var = tk.StringVar(value="PRIORITY (З пріоритетом)")
        self.d_var = tk.StringVar(value="ROUND_ROBIN (...)")
        self.t_var = tk.StringVar(value="Hypercube (Гіперкуб)")
        
        for lbl, var, vals in [
            ("Алгоритм черги:", self.q_var, ["FIFO (Жива черга)", "LIFO (Стек)", "PRIORITY (З пріоритетом)"]),
            ("Балансування:", self.d_var, [s + " (...)" for s in self.strats]),
            ("Топологія:", self.t_var, list(TOPOLOGY_CONFIG.keys()))
        ]:
            ttk.Label(ctrl, text=lbl, font=("Arial", 9, "bold")).pack(anchor='w', padx=10, pady=(5, 0))
            cb = ttk.Combobox(ctrl, textvariable=var, values=vals, state="readonly")
            cb.pack(fill='x', padx=10)
            
            if lbl == "Топологія:":
                cb.bind("<<ComboboxSelected>>", self.on_topo_dropdown_change)

        self.btn = ttk.Button(ctrl, text="▶️ ЗАПУСТИТИ", command=self.start_sim)
        self.btn.pack(pady=(20, 5), fill='x', padx=10)
        
        self.pause_btn = ttk.Button(ctrl, text="⏸ ПАУЗА", command=self.toggle_pause, state="disabled")
        self.pause_btn.pack(pady=(0, 20), fill='x', padx=10)

        log_fr = ttk.LabelFrame(self.root, text="Лог подій")
        log_fr.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.log_area = scrolledtext.ScrolledText(log_fr, font=("Consolas", 9))
        self.log_area.pack(fill='both', expand=True, padx=5, pady=5)

        right = tk.Frame(self.root)
        right.grid(row=0, column=2, sticky="nsew", padx=(0, 10), pady=10)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        
        net_frame = ttk.LabelFrame(right, text="Мережа")
        net_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        self.canvas = tk.Canvas(net_frame, bg="#E6F0FF")
        self.canvas.pack(fill='both', expand=True, padx=5, pady=5)
        self.canvas.bind("<Configure>", lambda e: self.on_topology_change())
        
        chart_frame = ttk.LabelFrame(right, text="Аналіз")
        chart_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        
        self.fig, self.ax = plt.subplots(figsize=(4, 3))
        self.fig.tight_layout()
        self.chart = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.chart.get_tk_widget().pack(fill='both', expand=True, padx=5, pady=5)
        
        self.update_chart()
        
        self.root.update_idletasks()
        self.root.after(100, self.on_topology_change)

    def validate_topology_workers(self, n, topo):
        cfg = TOPOLOGY_CONFIG.get(topo)
        if not cfg:
            return True, ""
            
        if n < cfg["min"] or n > cfg["max"]:
            return False, f"❌ Для '{topo}' діапазон: від {cfg['min']} до {cfg['max']}. {cfg['hint']}"

        if "Hypercube" in topo:
            if n <= 0 or (n & (n - 1)) != 0:
                return False, f"❌ Для Гіперкуба кількість має бути степенем двійки (2, 4, 8, 16)! {cfg['hint']}"
                
        if "Tree" in topo:
            allowed_trees = [1, 3, 7, 15, 31]
            if n not in allowed_trees:
                return False, f"❌ Для Дерева оберіть повні рівні: {allowed_trees}! {cfg['hint']}"

        return True, f"ℹ️ {cfg['hint']}"

    def on_topo_dropdown_change(self, event=None):
        topo = self.t_var.get()
        cfg = TOPOLOGY_CONFIG.get(topo)
        if cfg:
            w_entry = self.inputs["Кількість воркерів:"]
            w_entry.delete(0, tk.END)
            w_entry.insert(0, str(cfg["default"]))
        self.on_topology_change()

    def log(self, msg): 
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.root.update()

    def draw_network(self, n, topo):
        self.canvas.delete("all")
        self.coords.clear()
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        if w < 10 or h < 10:
            w, h = 450, 360 

        cx, cy, r = w / 2, h / 2, min(w, h) / 3
        
        bx, by = (cx, 30) if topo in ["Tree (Дерево)", "Hypercube (Гіперкуб)"] else (cx, cy)
        
        merged_broker_topos = ["Hypercube (Гіперкуб)", "Tree (Дерево)", "Star (Зірка)", "Mesh (Повнозв'язна)"]
        
        if topo not in merged_broker_topos:
            self.coords['B'] = (bx, by)
            self.canvas.create_rectangle(bx-20, by-20, bx+20, by+20, fill="#FFD700", outline="black", tags="node")
            self.canvas.create_text(bx, by, text="Broker", font=("Arial", 8, "bold"))

        try:
            loss_val = float(self.inputs["Втрата пакетів W_last %:"].get())
        except ValueError:
            loss_val = 0.0

        max_lvl = n.bit_length() if n > 0 else 1
        y_step = (h - 70) / max(max_lvl, 1)

        for i in range(1, n + 1):
            if "Tree" in topo:
                lvl = i.bit_length()
                start_idx = 1 << (lvl - 1)
                end_idx = min(n, (1 << lvl) - 1)
                count_on_lvl = end_idx - start_idx + 1
                pos_on_lvl = i - start_idx + 1
                
                wx = (w / (count_on_lvl + 1)) * pos_on_lvl
                wy = 35 + lvl * min(75, y_step)
            
            elif "Hypercube" in topo:
                idx = i - 1
                bit_x = idx & 1
                bit_y = (idx >> 1) & 1
                bit_z = (idx >> 2) & 1
                bit_w = (idx >> 3) & 1
                
                scale = min(w, h) * 0.22 if n > 8 else min(w, h) * 0.28
                
                dx = (1 if bit_x else -1) * scale
                dy = (1 if bit_y else -1) * scale * 0.75
                dz_x = (1 if bit_z else -1) * (scale * 0.45)
                dz_y = (-1 if bit_z else 1) * (scale * 0.30)
                
                w_scale = 0.55 if bit_w == 0 else 1.0
                grid_cy = (h + 30) / 2
                
                wx = cx + (dx + dz_x) * w_scale
                wy = grid_cy + (dy + dz_y) * w_scale
            
            else:
                if topo in ["Star (Зірка)", "Mesh (Повнозв'язна)"] and i == 1:
                    wx, wy = cx, cy
                else:
                    nodes_on_ring = n - 1 if topo in ["Star (Зірка)", "Mesh (Повнозв'язна)"] else n
                    idx_on_ring = i - 2 if topo in ["Star (Зірка)", "Mesh (Повнозв'язна)"] else i - 1
                    
                    if nodes_on_ring > 0:
                        ang = (2 * math.pi / nodes_on_ring) * idx_on_ring - math.pi/2
                        wx, wy = cx + r * math.cos(ang), cy + r * math.sin(ang)
                    else:
                        wx, wy = cx, cy

            self.coords[i] = (wx, wy)
            
            if topo in merged_broker_topos and i == 1:
                col = "#FFD700"
                txt = "B/W1"
                self.coords['B'] = (wx, wy)
            else:
                col = "#FF9999" if (i == n and loss_val > 0) else "#90EE90"
                txt = f"W{i}"
                
            self.canvas.create_oval(wx-15, wy-15, wx+15, wy+15, fill=col, outline="black", tags="node")
            self.canvas.create_text(wx, wy, text=txt)

            if "Tree" in topo:
                p = i // 2
                if p > 0:
                    parent_coord = self.coords[p]
                    self.canvas.create_line(parent_coord[0], parent_coord[1], wx, wy, fill="lightgray", width=2, tags=f"link_{p}_{i}")
            
            elif "Ring" in topo:
                if i == 1: 
                    self.canvas.create_line(bx, by, wx, wy, fill="lightgray", width=2, tags="link_B_1")
                else:
                    prev = i - 1
                    self.canvas.create_line(self.coords[prev][0], self.coords[prev][1], wx, wy, fill="lightgray", width=2, tags=f"ring_{prev}_{i}")
                
                if i == n and n > 1:
                    self.canvas.create_line(wx, wy, self.coords[1][0], self.coords[1][1], fill="lightgray", width=2, tags=f"ring_{n}_1")
            
            elif "Hypercube" in topo:
                for j in range(1, i):
                    val1, val2 = i - 1, j - 1
                    if (val1 ^ val2) & ((val1 ^ val2) - 1) == 0:
                        self.canvas.create_line(self.coords[j][0], self.coords[j][1], wx, wy, fill="lightgray", width=2, tags=f"cube_{j}_{i}")
            else: 
                if i > 1 or topo not in merged_broker_topos:
                    self.canvas.create_line(self.coords['B'][0], self.coords['B'][1], wx, wy, fill="lightgray", width=2, tags=f"link_B_{i}")
                
                if "Mesh" in topo:
                    for j in range(2, i): 
                        self.canvas.create_line(self.coords[j][0], self.coords[j][1], wx, wy, fill="lightgray", dash=(2,2), tags=f"mesh_{j}_{i}")
        
        self.canvas.tag_raise("node")

    def highlight_path(self, w_id):
        for line in self.active_lines: 
            tags = self.canvas.gettags(line)
            if any(t.startswith("mesh_") for t in tags):
                self.canvas.itemconfig(line, fill="lightgray", width=1, dash=(2,2))
            else:
                self.canvas.itemconfig(line, fill="lightgray", width=2, dash=())
        self.active_lines.clear()
        
        if not w_id: 
            return self.root.update()

        topo, tags = self.t_var.get(), []
        merged_broker_topos = ["Hypercube (Гіперкуб)", "Tree (Дерево)", "Star (Зірка)", "Mesh (Повнозв'язна)"]
        
        if "Tree" in topo:
            curr = w_id
            while curr > 1:
                tags.append(f"link_{curr//2}_{curr}")
                curr //= 2
        elif "Ring" in topo:
            n = len([k for k in self.coords.keys() if isinstance(k, int)])
            forward_steps = w_id - 1
            backward_steps = n - forward_steps
            if forward_steps <= backward_steps:
                tags = ["link_B_1"] + [f"ring_{i}_{i+1}" for i in range(1, w_id)]
            else:
                tags = ["link_B_1", f"ring_{n}_1"] + [f"ring_{i}_{i+1}" for i in range(n-1, w_id-1, -1)]
        elif "Hypercube" in topo:
            tags = []
            curr = 0
            target = w_id - 1
            while curr != target:
                diff = curr ^ target
                step = diff & -diff 
                next_node = curr ^ step
                n1, n2 = sorted([curr + 1, next_node + 1])
                tags.append(f"cube_{n1}_{n2}")
                curr = next_node
        elif "Mesh" in topo:
            if w_id == 1:
                tags = []
            else:
                import random
                node_count = len([k for k in self.coords.keys() if isinstance(k, int)])
                if node_count > 2 and random.choice([True, False]):
                    available = [x for x in range(2, node_count + 1) if x != w_id]
                    if available:
                        inter = random.choice(available)
                        tags.append(f"link_B_{inter}")
                        n1, n2 = sorted([inter, w_id])
                        tags.append(f"mesh_{n1}_{n2}")
                    else:
                        tags = [f"link_B_{w_id}"]
                else:
                    tags = [f"link_B_{w_id}"]
        else: 
            if topo in merged_broker_topos and w_id == 1:
                tags = []
            else:
                tags = [f"link_B_{w_id}"]

        for t in tags:
            for item in self.canvas.find_withtag(t):
                self.canvas.itemconfig(item, fill="red", width=4, dash=())
                self.active_lines.append(item)
        self.root.update()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_btn.config(text="▶️ ПРОДОВЖИТИ")
            self.log("⏸ Симуляцію призупинено.")
        else:
            self.pause_btn.config(text="⏸ ПАУЗА")
            self.log("▶️ Симуляцію відновлено.")

    def start_sim(self):
        self.log_area.delete('1.0', tk.END)
        
        try:
            n_w = int(self.inputs["Кількість воркерів:"].get())
            n_msg = int(self.inputs["Кількість повідомлень:"].get())
            intensity = float(self.inputs["Інтенсивність:"].get())
            loss = float(self.inputs["Втрата пакетів W_last %:"].get())
        except ValueError: 
            self.log("❌ Помилка вводу! Перевірте правильність числових значень.")
            return

        topo = self.t_var.get()
        is_valid, msg = self.validate_topology_workers(n_w, topo)
        if not is_valid:
            self.log(msg)
            self.log("⚠️ Запуск заблоковано: введіть коректне значення кількості воркерів з урахуванням топології.")
            return

        self.btn.config(state="disabled")
        self.is_paused = False
        self.pause_btn.config(state="normal", text="⏸ ПАУЗА")

        q_strat = self.q_var.get().split()[0]
        d_strat = self.d_var.get().split()[0]

        if (n_w, n_msg, loss, q_strat, intensity) != self.params:
            self.params = (n_w, n_msg, loss, q_strat, intensity)
            
            self.results = {k: 0.0 for k in self.results} 
            self.base_msgs.clear()
            
            curr = 0
            for i in range(n_msg):
                curr += random.expovariate(intensity)
                ip = f"192.168.1.{random.randint(1,10)}"
                self.base_msgs.append(Message(i, random.randint(50, 300), curr, 1 if random.random() < 0.3 else 3, ip))
            self.log("🔄 Нові умови! Згенеровано набір.")

        self.draw_network(n_w, topo)
        
        workers = [Worker(i+1, 100 if i == n_w-1 else 200, 0.5 if i == n_w-1 else 0.05, loss if i == n_w-1 else 0.0) for i in range(n_w)]
        self.broker = Broker(workers, d_strat, q_strat, self.log)
        self.broker.add_messages(copy.deepcopy(self.base_msgs))
        
        self.sim_time = 0
        self.run_d = d_strat
        self.run_q = q_strat
        
        self.log(f"\n📺 Запуск: {d_strat} + {q_strat}...")
        self.step()

    def step(self):
        if self.is_paused:
            self.root.after(100, self.step)
            return

        if getattr(self.broker, 'future_msgs', []) or getattr(self.broker, 'ready_queue', []):
            msg, worker, self.sim_time = self.broker.run_step(self.sim_time)
            
            if msg and worker:
                self.highlight_path(worker.id)
                ip_info = f" (IP:{msg.sender_ip})" if getattr(self, 'run_d', '') == "IP_HASH" else ""
                self.log(f"➡️ {msg}{ip_info} -> W{worker.id}")
            
            self.root.after(100, self.step)
            
        else:
            self.log(f"🏁 Завершено!")
            self.highlight_path(None)
            self.btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            
            avg = sum(m.finished_at - m.created_at for m in self.broker.processed) / len(self.broker.processed) if self.broker.processed else 0
            self.results[self.run_d] = avg
            dropped_n = len(getattr(self.broker, 'dropped', []))
            self.log(f"\n📊 Час: {avg:.2f} сек. (оброблено: {len(self.broker.processed)}, втрачено: {dropped_n})")
            self.update_chart()

    def update_chart(self):
        self.ax.clear()
        vals = [self.results[s] for s in self.strats]
        
        self.ax.bar(['RR', 'WRR', 'LC', 'WLC', 'IP-H', 'LRT'], vals, color=['#ff6666', '#ff9966', '#ffff66', '#99ff99', '#99ccff', '#cc99ff'])
        
        title = f"Час обробки ({getattr(self, 'run_q', 'N/A')})"
        self.ax.set_title(title, fontsize=10)
        self.ax.set_ylabel("Секунди")
        self.ax.tick_params(axis='x', labelsize=8)
        
        for i, v in enumerate(vals):
            if v > 0: 
                self.ax.text(i, v, f"{v:.2f}", ha='center', va='bottom', fontsize=8)
                
        self.fig.tight_layout()
        self.chart.draw()

    def on_topology_change(self, event=None):
        self.root.update_idletasks()
        topo = self.t_var.get()
        try:
            n_w = int(self.inputs["Кількість воркерів:"].get())
        except ValueError:
            self.topo_hint_lbl.config(text="⚠️ Введіть коректне ціле число", foreground="red")
            return
            
        is_valid, msg = self.validate_topology_workers(n_w, topo)
        if not is_valid:
            self.topo_hint_lbl.config(text=msg, foreground="red")
        else:
            self.topo_hint_lbl.config(text=msg, foreground="gray")
            self.draw_network(n_w, topo)
