from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class PromptDefinition(BaseModel):
    key: str
    templates: Dict[str, str]  # language -> template
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class PromptKey(BaseModel):
    namespace: str
    name: str

    @property
    def full_key(self) -> str:
        return f"{self.namespace}.{self.name}"

    @classmethod
    def from_str(cls, key: str) -> "PromptKey":
        parts = key.rsplit(".", 1)
        if len(parts) == 1:
            return cls(namespace="", name=parts[0])
        return cls(namespace=parts[0], name=parts[1])
