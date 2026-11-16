import math

TOPOLOGY_CONFIG = {
    "Star (Зірка)": {
        "min": 1,
        "max": 32,
        "default": 8,
        "allowed_values": None,  # Будь-яке ціле число в межах [min, max]
        "hint": "Кількість воркерів необмежена (N ≥ 1). Брокер напряму надсилає кожному вузлу.",
        "validate": lambda n: (
            (1 <= n <= 32),
            "Кількість воркерів для топології 'Зірка' має бути в діапазоні від 1 до 32."
        ),
        "formulas": {
            "links_count": lambda n: n,
            "diameter": lambda n: 1,
            "max_degree": lambda n: n,
        },
    },
    "Ring (Кільце)": {
        "min": 2,
        "max": 24,
        "default": 8,
        "allowed_values": None,
        "hint": "Мінімум 2 воркери (N ≥ 2). Повідомлення передаються по ланцюжку через сусідів.",
        "validate": lambda n: (
            (2 <= n <= 24),
            "Кількість воркерів для топології 'Кільце' має бути від 2 до 24."
        ),
        "formulas": {
            "links_count": lambda n: n + 1,
            "diameter": lambda n: math.floor(n / 2) + 1,
            "max_degree": lambda n: 2 if n > 2 else 1,
        },
    },
    "Tree (Дерево)": {
        "min": 1,
        "max": 31,
        "default": 7,
        "allowed_values": [1, 3, 7, 15, 31],
        "hint": "Треба вводити 1, 3, 7, 15 або 31 воркер (2^k - 1) для побудови збалансованого двійкового дерева.",
        "validate": lambda n: (
            n in [1, 3, 7, 15, 31],
            "Для топології 'Дерево' оберіть кількість із фіксованих рівнів: 1, 3, 7, 15 або 31."
        ),
        "formulas": {
            "links_count": lambda n: n,
            "diameter": lambda n: n.bit_length(),
            "max_degree": lambda n: 3,
        },
    },
    "Hypercube (Гіперкуб)": {
        "min": 2,
        "max": 16,
        "default": 8,
        "allowed_values": [2, 4, 8, 16],
        "hint": "Степені 2^k (2, 4, 8, 16). Для 8 воркерів — 3D-куб, для 16 — 4D-гіперкуб.",
        "validate": lambda n: (
            (n in [2, 4, 8, 16]),
            "Для топології 'Гіперкуб' кількість воркерів має бути степенем двійки: 2, 4, 8 або 16."
        ),
        "formulas": {
            "links_count": lambda n: int(n * math.log2(n) / 2) + 1 if n > 0 and (n & (n - 1)) == 0 else 0,
            "diameter": lambda n: math.ceil(math.log2(n)) if n > 0 else 0,
            "max_degree": lambda n: math.ceil(math.log2(n)) if n > 0 else 0,
        },
    },
    "Mesh (Повнозв'язна)": {
        "min": 2,
        "max": 12,
        "default": 6,
        "allowed_values": None,
        "hint": "Рекомендовано від 2 до 12 воркерів, щоб лінії між усіма вузлами не перекривали одне одного.",
        "validate": lambda n: (
            (2 <= n <= 12),
            "Кількість воркерів для топології 'Повнозв'язна' має бути від 2 до 12."
        ),
        "formulas": {
            "links_count": lambda n: n + (n * (n - 1)) // 2,
            "diameter": lambda n: 1,
            "max_degree": lambda n: n - 1,
        },
    },
}

def validate_topology(topo_name: str, workers_count: int) -> tuple[bool, str]:
    """
    Перевіряє коректність кількості воркерів для обраної топології.
    Повертає кортеж (is_valid, message).
    """
    cfg = TOPOLOGY_CONFIG.get(topo_name)
    if not cfg:
        return False, f"Топологія '{topo_name}' не знайдена в конфігурації."
    
    validator = cfg.get("validate")
    if validator:
        is_valid, error_msg = validator(workers_count)
        if not is_valid:
            return False, f"❌ {error_msg} (Введіть інше значення з урахуванням обмежень: {cfg['hint']})"
            
    return True, f"ℹ️ {cfg['hint']}"