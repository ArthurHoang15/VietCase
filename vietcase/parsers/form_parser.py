from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from bs4 import BeautifulSoup, Tag

from vietcase.parsers.compatibility import normalize_whitespace


@dataclass(slots=True)
class ParsedField:
    logical_key: str
    kind: str
    name: str
    control_id: str
    label: str
    selector: str
    options: list[dict[str, str]]
    current_value: str = ""
    checked: bool = False
    priority: int = 0
    aliases: list[dict[str, object]] = field(default_factory=list)


class FormParser:
    CONTROL_KEY_MAP = {
        'ctl00_Content_home_Public_ctl00_txtKeyword_top': ('keyword', 20),
        'ctl00_Content_home_Public_ctl00_Drop_Levels_top': ('court_level', 20),
        'ctl00_Content_home_Public_ctl00_Ra_Drop_Courts_top': ('court', 20),
        'ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH_top': ('adjudication_level', 20),
        'ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH_top': ('document_type', 20),
        'ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH_top': ('case_style', 20),
        'ctl00_Content_home_Public_ctl00_Ra_Case_shows_search_top': ('legal_relation', 20),
        'ctl00_Content_home_Public_ctl00_Rad_DATE_FROM_top': ('date_from', 20),
        'ctl00_Content_home_Public_ctl00_Rad_DATE_TO_top': ('date_to', 20),
        'ctl00_Content_home_Public_ctl00_check_anle_top': ('precedent_applied', 20),
        'ctl00_Content_home_Public_ctl00_check_anle_voted_top': ('precedent_voted', 20),
        'ctl00_Content_home_Public_ctl00_txtKeyword': ('keyword', 10),
        'ctl00_Content_home_Public_ctl00_Drop_Levels': ('court_level', 10),
        'ctl00_Content_home_Public_ctl00_Ra_Drop_Courts': ('court', 10),
        'ctl00_Content_home_Public_ctl00_Drop_LEVEL_JUDGMENT_SEARCH': ('adjudication_level', 10),
        'ctl00_Content_home_Public_ctl00_Drop_STATUS_JUDGMENT_SEARCH': ('document_type', 10),
        'ctl00_Content_home_Public_ctl00_Drop_CASES_STYLES_SEARCH': ('case_style', 10),
        'ctl00_Content_home_Public_ctl00_Ra_Case_shows_search': ('legal_relation', 10),
        'ctl00_Content_home_Public_ctl00_Rad_DATE_FROM': ('date_from', 10),
        'ctl00_Content_home_Public_ctl00_Rad_DATE_TO': ('date_to', 10),
        'ctl00_Content_home_Public_ctl00_check_anle': ('precedent_applied', 10),
        'ctl00_Content_home_Public_ctl00_check_anle_voted': ('precedent_voted', 10),
    }

    def parse_hidden_fields(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, 'html.parser')
        return {control['name']: control.get('value', '') for control in soup.select("input[type='hidden'][name]")}

    def parse_form_state(self, html: str) -> dict[str, object]:
        soup = BeautifulSoup(html, 'html.parser')
        fields: dict[str, dict[str, object]] = {}
        for select in soup.select('select'):
            field = self._build_select_field(select)
            if field:
                self._store_field(fields, field)
        for input_control in soup.select('input'):
            field = self._build_input_field(input_control)
            if field:
                self._store_field(fields, field)
        pagination_name = ''
        pagination_select = soup.select_one('#ctl00_Content_home_Public_ctl00_DropPages') or soup.select_one("select[id*='DropPages']")
        if pagination_select:
            pagination_name = pagination_select.get('name', '')
        search_button_name = ''
        button = soup.select_one('#ctl00_Content_home_Public_ctl00_cmd_search_banner') or soup.select_one("input[id*='cmd_search_banner']")
        if button:
            search_button_name = button.get('name', '')
        selects = {key: value['options'] for key, value in fields.items() if value['kind'] == 'select'}
        return {
            'hidden_fields': self.parse_hidden_fields(html),
            'fields': fields,
            'selects': selects,
            'pagination_name': pagination_name,
            'search_button_name': search_button_name,
        }

    def parse_select_options(self, html: str) -> dict[str, list[dict[str, str]]]:
        return self.parse_form_state(html)['selects']

    def _store_field(self, fields: dict[str, dict[str, object]], field: ParsedField) -> None:
        current = fields.get(field.logical_key)
        incoming = asdict(field)
        if current:
            merged_aliases: dict[tuple[str, str], dict[str, object]] = {}
            for alias in current.get('aliases', []):
                merged_aliases[(str(alias.get('name', '')), str(alias.get('control_id', '')))] = alias
            for alias in incoming.get('aliases', []):
                merged_aliases[(str(alias.get('name', '')), str(alias.get('control_id', '')))] = alias
            if int(current.get('priority', 0)) > field.priority:
                current['aliases'] = sorted(
                    merged_aliases.values(),
                    key=lambda item: (-int(item.get('priority', 0)), str(item.get('name', ''))),
                )
                fields[field.logical_key] = current
                return
            incoming['aliases'] = sorted(
                merged_aliases.values(),
                key=lambda item: (-int(item.get('priority', 0)), str(item.get('name', ''))),
            )
        fields[field.logical_key] = incoming

    def _build_select_field(self, select: Tag) -> ParsedField | None:
        resolved = self._resolve_logical_key(select)
        if not resolved:
            return None
        logical_key, priority = resolved
        control_id = select.get('id', '')
        return ParsedField(
            logical_key=logical_key,
            kind='select',
            name=select.get('name', ''),
            control_id=control_id,
            label=self._resolve_label(select),
            selector=f"#{control_id}" if control_id else f"select[name='{select.get('name', '')}']",
            options=[{'value': normalize_whitespace(option.get('value', '')), 'label': normalize_whitespace(option.get_text(' ', strip=True))} for option in select.select('option')],
            current_value=self._selected_option_value(select),
            priority=priority,
            aliases=[self._build_alias(select, priority, 'select')],
        )

    def _build_input_field(self, control: Tag) -> ParsedField | None:
        input_type = (control.get('type') or 'text').lower()
        if input_type not in {'text', 'search', 'checkbox'}:
            return None
        resolved = self._resolve_logical_key(control)
        if not resolved:
            return None
        logical_key, priority = resolved
        control_id = control.get('id', '')
        return ParsedField(
            logical_key=logical_key,
            kind='checkbox' if input_type == 'checkbox' else 'input',
            name=control.get('name', ''),
            control_id=control_id,
            label=self._resolve_label(control),
            selector=f"#{control_id}" if control_id else f"input[name='{control.get('name', '')}']",
            options=[],
            current_value=normalize_whitespace(control.get('value', '')),
            checked=control.has_attr('checked'),
            priority=priority,
            aliases=[self._build_alias(control, priority, 'checkbox' if input_type == 'checkbox' else 'input')],
        )

    def _build_alias(self, control: Tag, priority: int, kind: str) -> dict[str, object]:
        name = control.get('name', '')
        control_id = control.get('id', '')
        selector = f"#{control_id}" if control_id else f"{'select' if kind == 'select' else 'input'}[name='{name}']"
        return {
            'name': name,
            'control_id': control_id,
            'selector': selector,
            'priority': priority,
            'kind': kind,
            'current_value': self._current_control_value(control),
            'checked': control.has_attr('checked'),
        }

    def _current_control_value(self, control: Tag) -> str:
        if control.name == 'select':
            return self._selected_option_value(control)
        return normalize_whitespace(control.get('value', ''))

    def _selected_option_value(self, select: Tag) -> str:
        selected = select.select_one('option[selected]')
        if selected:
            return normalize_whitespace(selected.get('value', ''))
        first = select.select_one('option')
        if first:
            return normalize_whitespace(first.get('value', ''))
        return ""

    def _resolve_logical_key(self, control: Tag) -> tuple[str, int] | None:
        control_id = control.get('id', '')
        name = control.get('name', '')
        for key in (control_id, name):
            if key in self.CONTROL_KEY_MAP:
                return self.CONTROL_KEY_MAP[key]
        haystack = ' '.join([name, control_id, control.get('placeholder', ''), self._resolve_label(control)]).lower()
        normalized = re.sub(r'\s+', ' ', haystack)
        if 'droppages' in normalized or 'cmd_search_banner' in normalized or 'cmd_left_search' in normalized:
            return None
        if 'txtkeyword' in normalized:
            return ('keyword', 1)
        if 'drop_levels' in normalized:
            return ('court_level', 1)
        if 'ra_drop_courts' in normalized:
            return ('court', 1)
        if 'drop_level_judgment_search' in normalized:
            return ('adjudication_level', 1)
        if 'drop_status_judgment_search' in normalized:
            return ('document_type', 1)
        if 'drop_cases_styles_search' in normalized:
            return ('case_style', 1)
        if 'ra_case_shows_search' in normalized:
            return ('legal_relation', 1)
        if 'rad_date_from' in normalized:
            return ('date_from', 1)
        if 'rad_date_to' in normalized:
            return ('date_to', 1)
        if 'check_anle_voted' in normalized:
            return ('precedent_voted', 1)
        if 'check_anle' in normalized:
            return ('precedent_applied', 1)
        return None

    def _resolve_label(self, control: Tag) -> str:
        control_id = control.get('id', '')
        if control_id:
            parent = control.find_parent()
            label = parent.find('label', attrs={'for': control_id}) if parent else None
            if label:
                return normalize_whitespace(label.get_text(' ', strip=True)).rstrip(':')
        previous = control.find_previous(['label'])
        if previous:
            text = normalize_whitespace(previous.get_text(' ', strip=True))
            if text:
                return text.rstrip(':')
        return normalize_whitespace(control.get('placeholder', ''))
