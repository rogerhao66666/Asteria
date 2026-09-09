from dataclasses import dataclass

FILTER_NEAREST = "nearest"
FILTER_LINEAR = "linear"
VALID_FILTERS = {FILTER_NEAREST, FILTER_LINEAR}


@dataclass(frozen=True, slots=True)
class PixelScalePolicy:
    virtual_width: int
    virtual_height: int
    filter_mode: str = FILTER_NEAREST
    integer_scale: bool = True

    def validate(self):
        if self.virtual_width <= 0 or self.virtual_height <= 0:
            raise ValueError("virtual resolution must be positive")
        if self.filter_mode not in VALID_FILTERS:
            raise ValueError("unsupported filter mode")

    def resolve(self, window_width, window_height):
        self.validate()
        if window_width <= 0 or window_height <= 0:
            raise ValueError("window size must be positive")
        sx = window_width / self.virtual_width
        sy = window_height / self.virtual_height
        scale = min(sx, sy)
        if self.integer_scale:
            scale = max(1.0, float(int(scale)))
        out_w = self.virtual_width * scale
        out_h = self.virtual_height * scale
        off_x = (window_width - out_w) / 2
        off_y = (window_height - out_h) / 2
        return scale, off_x, off_y, out_w, out_h
