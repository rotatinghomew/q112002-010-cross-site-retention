#!/usr/bin/env python3
"""命令行入口：输出整批匹配保持率区间、外联复核与核实排期。

用法：
  python3 audit.py                      # 以资料中最大获知日为截止
  python3 audit.py --as-of 24           # 重放某历史时点
  python3 audit.py --locks              # 重放 locks 中的全部例会截止点
  python3 audit.py --json out.json      # 同时落一份机器可读快照
  python3 audit.py records2             # 读取同格式的其他资料目录
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_reader import read_records  # noqa: E402
from retention_audit.report import render_report  # noqa: E402
from retention_audit.snapshots import lock_snapshots, snapshot_at  # noqa: E402


def _default_as_of(tables):
    days = [row["day"] for row in tables["links"]]
    days += [row["day"] for row in tables["review_windows"]]
    days += [row["ready"] for row in tables["review_packages"]]
    return max(days)


def _json_default(obj):
    if isinstance(obj, frozenset):
        return sorted(obj)
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"不可序列化的类型 {type(obj)!r}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="跨考点复测配对保持率审计")
    parser.add_argument("folder", nargs="?", default=None,
                        help="资料目录（默认 records/）")
    parser.add_argument("--as-of", type=int, default=None,
                        help="资料获知截止日（默认取资料中最大日期）")
    parser.add_argument("--locks", action="store_true",
                        help="重放 locks 中的全部例会截止点")
    parser.add_argument("--json", dest="json_path", default=None,
                        help="把机器可读快照写入该文件")
    args = parser.parse_args(argv)

    folder = Path(args.folder) if args.folder else None
    tables = read_records(folder) if folder is not None else read_records()
    as_of = args.as_of if args.as_of is not None else _default_as_of(tables)

    if args.locks:
        payload = {"locks": lock_snapshots(tables)}
        print(render_report(payload["locks"][-1]["snapshot"]))
        for item in payload["locks"][:-1]:
            print("\n")
            print("#" * 60)
            print(f"例会 {item['issue']} 截止日第 {item['snapshot']['as_of']} 天")
            print("#" * 60)
            print(render_report(item["snapshot"]))
    else:
        payload = snapshot_at(tables, as_of)
        print(render_report(payload))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2,
                       default=_json_default),
            encoding="utf-8")
        print(f"\n机器可读快照已写入 {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
