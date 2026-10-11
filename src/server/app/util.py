"""通用工具：分页、参考计数、JSON 解析。"""
import json

PAGE_MAX = 200


def page_params(page: int = 1, size: int = 20):
    page = max(1, page)
    size = min(max(1, size), PAGE_MAX)
    return page, size, (page - 1) * size


def ref_count(conn, table: str, col: str, value: str) -> int:
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (value,)).fetchone()[0]


def parse_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text
