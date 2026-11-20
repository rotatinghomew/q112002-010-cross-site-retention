from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent / "records"


def read_records(folder=ROOT):
    """读取登记表原始行，不合并业务记录。"""
    schema = json.loads((folder / "catalog.json").read_text(encoding="utf-8"))
    tables = {}
    for table, columns in schema.items():
        rows = json.loads((folder / f"{table}.json").read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{table} 不是行数组")
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict) or set(row) != set(columns):
                raise ValueError(f"{table} 第 {index} 行字段与目录不符")
        tables[table] = rows
    return tables


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    for table, rows in read_records(folder).items():
        print(f"{table}: {len(rows)} 条登记")
