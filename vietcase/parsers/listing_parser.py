from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from vietcase.parsers.compatibility import BASE_URL, extract_regex, first_present, make_document_id, normalize_date, normalize_whitespace


class ListingParser:
    def parse(self, html: str, page_index: int = 1) -> dict[str, object]:
        soup = BeautifulSoup(html, "html.parser")
        total_results_text = soup.select_one('#ctl00_Content_home_Public_ctl00_lbl_count_record')
        total_pages_text = soup.select_one('#ctl00_Content_home_Public_ctl00_LbShowtotal')
        total_results = int(extract_regex(r'(\d[\d\.]*)', total_results_text.get_text(' ', strip=True) if total_results_text else '').replace('.', '') or 0)
        total_pages = int(extract_regex(r'(\d+)', total_pages_text.get_text(' ', strip=True) if total_pages_text else '') or 0)

        records: list[dict[str, object]] = []
        anchors = soup.select('#List_group_pub a.echo_id_pub[href*="chi-tiet-ban-an"]')
        for result_index, anchor in enumerate(anchors, start=1):
            item = self._extract_item(anchor)
            if not item:
                continue
            item['page_index'] = page_index
            item['result_index'] = result_index
            records.append(item)
        return {'total_results': total_results, 'total_pages': total_pages, 'results': records}

    def _extract_item(self, anchor: Tag) -> dict[str, object] | None:
        href = anchor.get('href', '')
        if not href:
            return None

        title_text = normalize_whitespace(anchor.get_text(' ', strip=True))
        heading_label = anchor.select_one('h4.list-group-item-heading label')
        heading_text = normalize_whitespace(heading_label.get_text(' ', strip=True)).rstrip(':') if heading_label else ''
        title_block = anchor.select_one('h4.list-group-item-heading span')
        title = normalize_whitespace(title_block.get_text(' ', strip=True)) if title_block else title_text
        scope = self._collect_item_scope(anchor)

        source_url = urljoin(BASE_URL, href)
        published_date = normalize_date(extract_regex(r'\((\d{2}[\./]\d{2}[\./]\d{4})\)', title_text))
        issued_date = normalize_date(first_present([
            extract_regex(r'(\d{2}[\./]\d{2}[\./]\d{4})', title),
            extract_regex(r'(\d{2}[\./]\d{2}[\./]\d{4})', title_text),
        ]))
        document_type = heading_text or ('Quy?t ??nh' if 'Quy?t ??nh' in title_text else 'B?n ?n' if 'B?n ?n' in title_text else '')
        document_number = extract_regex(r'([0-9][0-9A-Za-z.\-/]*(?:/[0-9A-Za-z.\-]+)+)', title)
        court_name = normalize_whitespace(first_present([
            extract_regex(r'c?a\s+(.+?)(?:\(|$)', title),
            self._court_name_from_title(title, issued_date),
        ]))

        rows = scope.select('.row')
        legal_relation = first_present([
            self._extract_labeled_value(scope, 'Quan h? ph?p lu?t'),
            self._extract_first_span(rows, 0, 0),
        ])
        adjudication_level = first_present([
            self._extract_labeled_value(scope, 'C?p x?t x?'),
            self._extract_first_span(rows, 1, 0),
        ])
        precedent_applied = first_present([
            self._extract_labeled_value(scope, '?p d?ng ?n l?'),
            self._extract_first_span(rows, 1, 1),
        ])
        case_style = first_present([
            self._extract_labeled_value(scope, 'Lo?i v?/vi?c'),
            self._extract_first_span(rows, 2, 0),
        ])
        correction_count = first_present([
            self._extract_labeled_value(scope, '??nh ch?nh'),
            self._extract_first_span(rows, 2, 1),
        ])
        summary_text = first_present([
            self._extract_labeled_value(scope, 'Th?ng tin v? v?/vi?c'),
            self._extract_labeled_value(scope, 'Th?ng tin v? v? ?n'),
            self._extract_description(scope),
        ])

        return {
            'source_url': source_url,
            'document_id': make_document_id(source_url),
            'title': title,
            'document_type': document_type,
            'document_number': document_number,
            'issued_date': issued_date,
            'published_date': published_date,
            'court_name': court_name,
            'case_style': case_style,
            'legal_relation': legal_relation,
            'adjudication_level': adjudication_level,
            'summary_text': summary_text,
            'precedent_applied': precedent_applied,
            'correction_count': correction_count,
        }

    def _collect_item_scope(self, anchor: Tag) -> Tag:
        parts = [str(anchor)]
        sibling = anchor.next_sibling
        while sibling is not None:
            if isinstance(sibling, Tag) and sibling.name == 'a' and 'echo_id_pub' in (sibling.get('class') or []):
                break
            if isinstance(sibling, Tag):
                parts.append(str(sibling))
            sibling = sibling.next_sibling
        scope_html = '<div>' + ''.join(parts) + '</div>'
        scope_soup = BeautifulSoup(scope_html, 'html.parser')
        return scope_soup.div or anchor

    def _extract_labeled_value(self, scope: Tag, label_text: str) -> str:
        for label in scope.select('label'):
            text = normalize_whitespace(label.get_text(' ', strip=True)).rstrip(':')
            if text != label_text:
                continue
            parent = label.parent if isinstance(label.parent, Tag) else None
            if parent:
                sibling = label.next_sibling
                while sibling is not None:
                    if isinstance(sibling, Tag):
                        value = normalize_whitespace(sibling.get_text(' ', strip=True))
                    else:
                        value = normalize_whitespace(str(sibling))
                    if value:
                        return value.lstrip(':').strip()
                    sibling = sibling.next_sibling
                parent_text = normalize_whitespace(parent.get_text(' ', strip=True))
                if parent_text.startswith(label_text):
                    stripped = normalize_whitespace(parent_text[len(label_text):].lstrip(':'))
                    if stripped:
                        return stripped
        return ''

    def _extract_first_span(self, rows: list[Tag], row_index: int, col_index: int) -> str:
        if row_index >= len(rows):
            return ''
        cols = rows[row_index].select('div[class*="col-"]')
        if col_index >= len(cols):
            return ''
        span = cols[col_index].find('span')
        return normalize_whitespace(span.get_text(' ', strip=True)) if span else ''

    def _extract_description(self, scope: Tag) -> str:
        description = scope.select_one('.Description_pub span') or scope.select_one('.Description_pub')
        if not description:
            return ''
        text = normalize_whitespace(description.get_text(' ', strip=True))
        return text.replace('Th?ng tin v? v?/vi?c:', '').replace('Th?ng tin v? v? ?n:', '').strip()

    def _court_name_from_title(self, title: str, issued_date: str) -> str:
        if not title:
            return ''
        source = title
        if issued_date:
            display_date = issued_date.replace('-', '/')
            index = title.find(display_date)
            if index >= 0:
                source = title[index + len(display_date):]
        source = source.split('(', 1)[0]
        parts = source.split(' c?a ', 1)
        if len(parts) == 2:
            return normalize_whitespace(parts[1])
        return ''
