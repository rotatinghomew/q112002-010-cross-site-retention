import sys
from pathlib import Path

# 支持 `python3 -I -m unittest discover -s tests`：隔离模式下根目录不在
# sys.path 中，而 record_reader 与 retention_audit 都位于仓库根。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
