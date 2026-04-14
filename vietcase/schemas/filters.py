from dataclasses import dataclass, field


@dataclass(slots=True)
class FilterOptions:
    hidden_fields: dict[str, str] = field(default_factory=dict)
    selects: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    source_mode: str = "requests"
