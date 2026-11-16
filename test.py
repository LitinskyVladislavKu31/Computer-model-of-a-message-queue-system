import random
import copy
from model import Message, Worker, Broker

def run_test(num_messages, num_workers=10, intensity=25.0, loss_percent=85.0, d_strat="", q_strat="FIFO"):
    print(f"\n--- Запуск тесту: {num_messages} повідомлень ---")
    print(f"Стратегія: {d_strat}, Черга: {q_strat}, Втрати: {loss_percent}%")

    workers = [Worker(i+1, 
                      100 if i == num_workers-1 else 200, 
                      0.5 if i == num_workers-1 else 0.05, 
                      loss_percent) 
               for i in range(num_workers)]
    msgs = []
    curr = 0
    for i in range(num_messages):
        curr += random.expovariate(intensity)
        ip = f"192.168.1.{random.randint(1,10)}"
        priority = 1 if random.random() < 0.3 else 3
        msgs.append(Message(i, random.randint(50, 300), curr, priority, ip))

    broker = Broker(workers, d_strat, q_strat, logger=None)
    broker.add_messages(copy.deepcopy(msgs))
    
    sim_time = 0
    while getattr(broker, 'future_msgs', []) or getattr(broker, 'ready_queue', []):
        msg, worker, sim_time = broker.run_step(sim_time)
    processed_count = len(broker.processed)
    dropped_count = len(getattr(broker, 'dropped', []))
    
    if processed_count > 0:
        avg_time = sum(m.finished_at - m.created_at for m in broker.processed) / processed_count
        print(f"✅ Оброблено повідомлень: {processed_count}")
        print(f"❌ Втрачено повідомлень: {dropped_count}")
        print(f"⏱ Середній час обробки: {avg_time:.4f} секунд")
    else:
        print("⚠️ Жодного повідомлення не було оброблено.")

if __name__ == "__main__":
    test_cases = [100, 300, 500, 700, 1000, 1300]
    
    for count in test_cases:
        run_test(num_messages=count, d_strat="WEIGHTED_ROUND_ROBIN")
