class BoundedSequenceGenerator:
    def __init__(self, max_value):
        self.current = 0
        self.max_value = max_value

    def __next__(self):
        self.current = (self.current + 1) % self.max_value
        val = self.current
        return val

    def __iter__(self):
        self.current = 0
        return self

    def set_to_last_seen(self, seq_number: int):
        self.current = seq_number
