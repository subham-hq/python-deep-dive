from abc import ABC, abstractmethod

from datapipe.models import Record


class ValidatingStep(ABC):
    @abstractmethod
    def validate(self, item: Record) -> None: ...

    def run(self, item: Record) -> Record:
        self.validate(item)
        return item

class RequirePositiveValue(ValidatingStep):
    def validate(self, item: Record) -> None:
        if item["value"] < 0:
            raise ValueError(f"negative value in record {item['id']}")

class RequiredName(ValidatingStep):
    def validate(self, item: Record) -> None:
        if not item["name"].strip():
            raise ValueError(f"record {item['id']} has an empty name")

