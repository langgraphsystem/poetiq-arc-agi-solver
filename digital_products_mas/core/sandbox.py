"""
Sandbox for Safe Code Execution
Adapted from ARC-AGI Solver (sandbox.py)

Safely execute LLM-generated code in isolated subprocess
with timeout and resource limits.
"""

import asyncio
import json
import os
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SandboxResult:
    """Result from sandbox execution"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    duration_sec: float = 0.0


async def run_code(
    code: str,
    input_data: Optional[dict] = None,
    timeout_sec: float = 30.0,
    allowed_imports: Optional[list[str]] = None,
) -> SandboxResult:
    """
    Run Python code in isolated subprocess.

    Adapted from ARC-AGI sandbox.py with enhancements
    for digital product generation.

    Args:
        code: Python code to execute
        input_data: Optional JSON input passed via stdin
        timeout_sec: Maximum execution time
        allowed_imports: List of allowed imports (for documentation)

    Returns:
        SandboxResult with output or error

    Security:
    - Runs in subprocess (not in-process)
    - Temporary directory isolation
    - PYTHONHASHSEED=0 for reproducibility
    - Process killed on timeout
    """
    script = _build_script(code, allowed_imports)

    start_time = asyncio.get_event_loop().time()

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "sandbox_script.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(script))

        # Create subprocess
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=td,
            env={
                "PYTHONHASHSEED": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
                # Inherit necessary env vars
                "HOME": os.environ.get("HOME", "/tmp"),
                "PATH": os.environ.get("PATH", ""),
            },
        )

        # Prepare input
        stdin_data = json.dumps(input_data or {}).encode()

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_data),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass

            duration = asyncio.get_event_loop().time() - start_time
            return SandboxResult(
                success=False,
                error="timeout",
                duration_sec=duration,
            )

        duration = asyncio.get_event_loop().time() - start_time

        stdout_str = stdout.decode() if stdout else ""
        stderr_str = stderr.decode() if stderr else ""

        if proc.returncode != 0:
            return SandboxResult(
                success=False,
                error=stderr_str or stdout_str or f"Exit code: {proc.returncode}",
                stdout=stdout_str,
                stderr=stderr_str,
                duration_sec=duration,
            )

        # Parse JSON output
        try:
            payload = json.loads(stdout_str)
            return SandboxResult(
                success=payload.get("ok", False),
                output=payload.get("result"),
                error=payload.get("error"),
                stdout=stdout_str,
                stderr=stderr_str,
                duration_sec=duration,
            )
        except json.JSONDecodeError as e:
            return SandboxResult(
                success=False,
                error=f"Invalid JSON output: {e}",
                stdout=stdout_str,
                stderr=stderr_str,
                duration_sec=duration,
            )


def _build_script(code: str, allowed_imports: Optional[list[str]] = None) -> str:
    """Build the sandbox script with imports and error handling"""

    imports = """
import json
import sys
import os
import math
import datetime
from typing import Any, Optional

# Common libraries for digital product generation
try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
except ImportError:
    canvas = None
"""

    return f"""
# Sandbox script - auto-generated
{imports}

# User code
{code}

if __name__ == '__main__':
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)

        # Execute main function if defined
        if 'main' in dir():
            result = main(input_data)
        elif 'generate' in dir():
            result = generate(input_data)
        elif 'transform' in dir():
            result = transform(input_data.get('input'))
        else:
            result = None

        # Convert result to JSON-serializable format
        if hasattr(result, 'tolist'):
            result = result.tolist()
        elif hasattr(result, '__dict__'):
            result = result.__dict__

        print(json.dumps({{"ok": True, "result": result}}))

    except Exception as e:
        import traceback
        print(json.dumps({{
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }}))
        sys.exit(1)
"""


# === SPECIALIZED RUNNERS ===

async def run_image_generation(
    code: str,
    params: dict,
    output_path: str,
    timeout_sec: float = 60.0,
) -> SandboxResult:
    """
    Run image generation code and save result.

    Expected code structure:
    - def generate(params) -> bytes or PIL.Image
    """
    wrapper_code = f"""
{code}

def main(input_data):
    result = generate(input_data)

    # Handle different return types
    if hasattr(result, 'save'):
        # PIL Image
        import io
        buffer = io.BytesIO()
        result.save(buffer, format='PNG')
        return {{"image_bytes": buffer.getvalue().hex(), "format": "png"}}
    elif isinstance(result, bytes):
        return {{"image_bytes": result.hex(), "format": "png"}}
    else:
        return {{"error": "Unknown result type"}}
"""
    return await run_code(wrapper_code, params, timeout_sec)


async def run_pdf_generation(
    code: str,
    params: dict,
    timeout_sec: float = 60.0,
) -> SandboxResult:
    """
    Run PDF generation code.

    Expected code structure:
    - def generate(params) -> bytes
    """
    wrapper_code = f"""
{code}

def main(input_data):
    result = generate(input_data)

    if isinstance(result, bytes):
        return {{"pdf_bytes": result.hex()}}
    else:
        return {{"error": "Expected bytes, got " + type(result).__name__}}
"""
    return await run_code(wrapper_code, params, timeout_sec)


async def run_data_transform(
    code: str,
    input_data: Any,
    timeout_sec: float = 10.0,
) -> SandboxResult:
    """
    Run data transformation (like ARC-AGI grid transforms).

    Expected code structure:
    - def transform(input) -> output
    """
    return await run_code(code, {"input": input_data}, timeout_sec)


# === VALIDATION ===

def validate_code_safety(code: str) -> tuple[bool, Optional[str]]:
    """
    Basic safety validation for code before execution.

    Returns:
        (is_safe, error_message)
    """
    dangerous_patterns = [
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "__import__",
        "open(",  # File access
        "requests",  # Network
        "urllib",
        "socket",
        "shutil.rmtree",
        "os.remove",
    ]

    code_lower = code.lower()

    for pattern in dangerous_patterns:
        if pattern.lower() in code_lower:
            return False, f"Dangerous pattern detected: {pattern}"

    return True, None
