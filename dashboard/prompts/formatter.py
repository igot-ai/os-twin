import re
from typing import Set, Any, Dict
from .exceptions import PromptValidationError

class PromptFormatter:
    def format(self, template: str, **kwargs) -> str:
        """Populate template with arguments."""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            missing_arg = str(e).strip("'")
            raise PromptValidationError(f"Missing required argument: {missing_arg}")
        except Exception as e:
            raise PromptValidationError(f"Formatting failed: {e}")

    def validate_args(self, template: str, kwargs: Dict[str, Any]) -> Set[str]:
        """Identify missing arguments in kwargs."""
        required = self.extract_placeholders(template)
        provided = set(kwargs.keys())
        return required - provided

    def extract_placeholders(self, template: str) -> Set[str]:
        """Extract all {placeholder} names from template."""
        # Simple regex for finding {placeholder} but ignoring {{escaped}}
        # This matches {name} but not {{name}} or {name:format}
        # A more robust way is using string.Formatter
        import string
        formatter = string.Formatter()
        return {name for _, name, _, _ in formatter.parse(template) if name is not None}
