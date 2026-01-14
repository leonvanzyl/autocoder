import os

from autocoder.core.gatekeeper import Gatekeeper


def test_allow_no_tests_accepts_missing_npm_test_script():
    prev = os.environ.get("AUTOCODER_YOLO_MODE")
    os.environ["AUTOCODER_YOLO_MODE"] = "1"
    res = {
        "success": True,
        "passed": False,
        "exit_code": 1,
        "command": "npm test",
        "output": 'npm ERR! Missing script: "test"\n',
        "errors": "",
    }
    try:
        out = Gatekeeper._apply_allow_no_tests(res, allow_no_tests=True)
        assert out["passed"] is True
        assert "No test script" in (out.get("note") or "")
    finally:
        if prev is None:
            os.environ.pop("AUTOCODER_YOLO_MODE", None)
        else:
            os.environ["AUTOCODER_YOLO_MODE"] = prev
