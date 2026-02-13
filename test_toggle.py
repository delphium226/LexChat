from server_py.src.config import settings
from server_py.src.agent.tools import MANAGER_TOOLS

def test_deep_research_toggle():
    print(f"Current enable_deep_research setting: {settings.enable_deep_research}")
    
    has_delegate = any(t['function']['name'] == 'delegate_research' for t in MANAGER_TOOLS)
    
    if settings.enable_deep_research:
        if has_delegate:
            print("PASS: Deep research enabled and tool is present.")
        else:
            print("FAIL: Deep research enabled but tool is MISSING.")
    else:
        if not has_delegate:
            print("PASS: Deep research disabled and tool is absent.")
        else:
            print("FAIL: Deep research disabled but tool is PRESENT.")

if __name__ == "__main__":
    test_deep_research_toggle()
