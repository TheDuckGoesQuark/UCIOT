class BoundedSequenceGenerator:
    def __init__(self, max_value):
        self.current = 0
        self.max_value = max_value

    def __next__(self):
        val = self.current
        self.current = (self.current + 1) % self.max_value
        return val

    def __iter__(self):
        self.current = 0
        return self
