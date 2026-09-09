from dataclasses import dataclass


@dataclass(slots=True)
class InputSnapshot:
    actions: dict[str, float]

    def axis(self, negative, positive):
        return float(self.actions.get(positive, 0.0)) - float(
            self.actions.get(negative, 0.0)
        )

    def movement_vector(self):
        return (
            self.axis("move_left", "move_right"),
            self.axis("move_up", "move_down"),
        )
