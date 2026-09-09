class HeadlessBackend:
    def __init__(self, close_after=1):
        self.frames = 0
        self.close_after = close_after
        self.closed = False

    def open(self, title, width, height):
        pass

    def tick(self, target_fps):
        return 1.0 / target_fps

    def begin_frame(self):
        pass

    def end_frame(self):
        self.frames += 1

    def should_close(self):
        return self.closed or self.frames >= self.close_after

    def close(self):
        self.closed = True
