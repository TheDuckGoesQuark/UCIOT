class Battery:
    def __init__(self, initial_max_sends):
        self.sends_left = initial_max_sends

    def remaining(self) -> int:
        return self.sends_left

    def decrement(self):
        self.sends_left -= 1
