import os
import sys
import types

# 把仓库根目录加入导入路径，便于直接 import agent
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 测试环境通常不安装 requests，这里注入占位模块，使导入 agent 不依赖网络/第三方包。
# 真正的 HTTP 调用在测试中通过 patch agent.requests.post 打桩。
try:
    import requests  # noqa: F401
except ImportError:
    requests_mod = types.ModuleType("requests")
    requests_mod.post = None
    sys.modules["requests"] = requests_mod
