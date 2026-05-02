import time

from collections import defaultdict, deque

class MessageTracker:
    def __init__(self, window_seconds: int = 12):
        self.window = window_seconds
        self.messages = defaultdict(deque)

    def add_message(self, user_id: int) -> int:
        now = time.time()
        queue = self.messages[user_id]

        while queue and now - queue[0] > self.window:
            queue.popleft()

        queue.append(now)

        return len(queue)