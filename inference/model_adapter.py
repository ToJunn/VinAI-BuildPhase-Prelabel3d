from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    @abstractmethod
    def predict(self, points, threshold):
        """Return canonical geometric-center boxes in the input LiDAR axes."""
