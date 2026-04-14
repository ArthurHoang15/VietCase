from __future__ import annotations

from bs4 import BeautifulSoup

from vietcase.parsers.compatibility import normalize_whitespace


class FormParser:
    def parse_hidden_fields(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        fields: dict[str, str] = {}
        for control in soup.select("input[type='hidden'][name]"):
            fields[control["name"]] = control.get("value", "")
        return fields

    def parse_select_options(self, html: str) -> dict[str, list[dict[str, str]]]:
        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, list[dict[str, str]]] = {}
        for select in soup.select("select[name]"):
            name = select.get("name", "")
            options: list[dict[str, str]] = []
            for option in select.select("option"):
                options.append(
                    {
                        "value": normalize_whitespace(option.get("value", "")),
                        "label": normalize_whitespace(option.get_text(" ", strip=True)),
                    }
                )
            result[name] = options
        return result
