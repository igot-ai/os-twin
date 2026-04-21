from abc import ABC, abstractmethod
from typing import Sequence

from llama_index.core.schema import BaseNode as Document


class DocParser(ABC):
    def __init__(self):
        self.type = "base"

    @abstractmethod
    def read(self, file, ws_id=None, node_id=None, **kwargs) -> Sequence[Document]:
        pass

    def to_unit_of_works(self, file, ws_id=None, node_id=None, **kwargs):
        return [
            {
                "type": self.type,
                "params": {
                    "file": file,
                    "ws_id": ws_id,
                    "node_id": node_id,
                    **kwargs,
                },
                "id": f"{str(file.get('url'))}-1",  # page id is 1 because we treat whole document as a page.
            }
        ]
