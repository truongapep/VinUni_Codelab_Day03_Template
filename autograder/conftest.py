import sys
import os

# Thêm thư mục starter-code vào sys.path để pytest có thể import
# template.py, agent.py, llm_utils.py, tools.py, ...
STARTER_CODE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "starter-code"
)
sys.path.insert(0, os.path.abspath(STARTER_CODE_DIR))