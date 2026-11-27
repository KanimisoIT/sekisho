#!/usr/bin/env python3
"""版の一致。.sekisho/config.json の version_sync に挙げたファイルから版の印を拾い、全部同じかを見る。

設定の例:
  {"version_sync": [{"file": "app.js", "pattern": "BUILD\\\\s*=\\\\s*(\\\\d+)"},
                    {"file": "version.json", "pattern": "\\"build\\"\\\\s*:\\\\s*(\\\\d+)"}]}
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import CONFIG, Report, load_json


def main():
    r = Report('版の一致')
    items = load_json(CONFIG, {}).get('version_sync', [])
    found = {}
    for it in items:
        path = pathlib.Path(it['file'])
        if not path.exists():
            r.fail('版の印のファイルが無い', it['file'], '設定にあるのに見つからない')
            continue
        m = re.search(it['pattern'], path.read_text(encoding='utf-8'))
        if not m:
            r.fail('版の印が拾えない', it['file'], it['pattern'])
            continue
        found[it['file']] = m.group(1)
    if len(set(found.values())) > 1:
        r.fail('版の印が食い違う', '、'.join(found), ' / '.join(f'{k}={v}' for k, v in found.items()))
    return r.finish()


if __name__ == '__main__':
    sys.exit(main())
