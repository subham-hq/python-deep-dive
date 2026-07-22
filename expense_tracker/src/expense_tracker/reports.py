from abc import ABC, abstractmethod

class Report(ABC):
    def header(self) -> str: ...

    @abstractmethod
    def render(self) -> str: ...