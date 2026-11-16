import random

class Message:
    def __init__(self, id, size, created_at, priority=1, sender_ip="N/A"):
        self.id = id
        self.size = size
        self.created_at = created_at
        self.priority = priority
        self.sender_ip = sender_ip
        self.finished_at = None
        
    def __repr__(self): 
        return f"[Msg#{self.id} {'VIP🔴' if self.priority == 1 else 'LOW⚪️'}]"


class Worker:
    def __init__(self, id, speed, latency, packet_loss):
        self.id = id
        self.speed = speed
        self.latency = latency
        self.packet_loss = packet_loss
        self.free_at = 0
        self.job_finish_times = []

    def active_connections(self, current_time):

        return sum(1 for t in self.job_finish_times if t > current_time)

    def process(self, msg, current_time, logger):
        delay, tries = self.latency, 1
        max_retries = 10 
        loss_chance = self.packet_loss / 100 if self.packet_loss > 1 else self.packet_loss

        dropped = False
        while random.random() < loss_chance:
            delay += self.latency
            tries += 1
            if logger:
                logger(f"⚠️ Worker {self.id}: Втрата пакету! (Спроба {tries})")
            if tries > max_retries:
                dropped = True
                break

        if dropped:
            if logger:
                logger(f"❌ Worker {self.id}: Збій доставки, повідомлення #{msg.id} втрачено!")
            msg.finished_at = None
            msg.dropped = True
            return None

        start = max(current_time, self.free_at)
        self.free_at = start + (msg.size / self.speed) + delay
        msg.finished_at = self.free_at
        self.job_finish_times.append(self.free_at)
        return self.free_at


class Broker:
    def __init__(self, workers, strategy, queue_type, logger):
        self.workers = workers
        self.strategy = strategy
        self.queue_type = queue_type
        self.log = logger
        
        self.future_msgs = []
        self.ready_queue = [] 
        self.processed = []
        self.dropped = [] 

        self.worker_idx = 0
        min_speed = min(w.speed for w in workers) if workers else 1
        self.wrr_weights = [max(1, round(w.speed / min_speed)) for w in workers]
        self.wrr_current = [0 for _ in workers]

    def add_messages(self, msgs):
        self.future_msgs = sorted(msgs, key=lambda x: x.created_at)

    def run_step(self, current_time):
        while self.future_msgs and self.future_msgs[0].created_at <= current_time:
            self.ready_queue.append(self.future_msgs.pop(0))
            
        if not self.ready_queue and self.future_msgs:
            current_time = self.future_msgs[0].created_at
            self.ready_queue.append(self.future_msgs.pop(0))
            
        if not self.ready_queue:
            return None, None, current_time
        if self.queue_type == "FIFO":
            idx = 0
        elif self.queue_type == "LIFO":
            idx = -1
        else: # PRIORITY
            idx = min(range(len(self.ready_queue)), key=lambda i: self.ready_queue[i].priority)
            
        msg = self.ready_queue.pop(idx)

        if self.queue_type == "PRIORITY":
            for m in self.ready_queue:
                if m.priority > 1 and (current_time - m.created_at > 5.0):
                    m.priority = 1
                    self.log(f"🔥 Msg #{m.id} -> VIP (Aging)")

        worker = self.get_worker(msg, current_time)
        result = worker.process(msg, current_time, self.log)

        if result is None:
            self.dropped.append(msg)
        else:
            self.processed.append(msg)

        return msg, worker, current_time

    def get_worker(self, msg, time):
        s = self.strategy
        if s == "ROUND_ROBIN": 
            w = self.workers[self.worker_idx]
            self.worker_idx = (self.worker_idx + 1) % len(self.workers)
            return w

        if s == "WEIGHTED_ROUND_ROBIN":
            total = sum(self.wrr_weights)
            for i in range(len(self.workers)):
                self.wrr_current[i] += self.wrr_weights[i]
            best = max(range(len(self.workers)), key=lambda i: self.wrr_current[i])
            self.wrr_current[best] -= total
            return self.workers[best]

        if s == "LEAST_CONNECTIONS":
            return min(self.workers, key=lambda w: w.active_connections(time))

        if s == "WEIGHTED_LEAST_CONNECTIONS":
            return min(self.workers, key=lambda w: w.active_connections(time) / w.speed)

        if s == "LEAST_RESPONSE_TIME":
            return min(self.workers, key=lambda w: max(0, w.free_at - time) + (msg.size / w.speed) + w.latency)
        
        return self.workers[sum(ord(c) for c in msg.sender_ip) % len(self.workers)]
