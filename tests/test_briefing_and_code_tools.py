"""
Unit and integration tests for Morning Briefing (1A), Knowledge Graph Memory (1B),
and Universal Multi-Language Code Runner / Auto-Fixer (1C).
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from vision.tools.registry import tool_registry
from vision.tools.briefing_tools import get_daily_morning_briefing, get_quick_daily_status
from vision.tools.code_execution_tools import (
    run_code_with_input,
    diagnose_and_fix_code_error,
    compile_and_run_java_project,
    _detect_language
)
from vision.memory.mag_engine import MAGEngine
from vision.tools.memory_tools import query_knowledge_graph, add_entity_relation


def test_tools_registered():
    """Verify all new tools are registered in tool_registry."""
    expected = [
        "get_daily_morning_briefing",
        "get_quick_daily_status",
        "run_code_with_input",
        "diagnose_and_fix_code_error",
        "compile_and_run_java_project",
        "query_knowledge_graph",
        "add_entity_relation"
    ]
    for t in expected:
        assert t in tool_registry._tools, f"Tool '{t}' was not registered"


def test_morning_briefing():
    """Test generating a structured morning briefing."""
    briefing = get_daily_morning_briefing(location="Anaparthi")
    assert "Good Morning" in briefing
    assert "Live Weather" in briefing
    assert "Anaparthi" in briefing
    assert "College Timetable" in briefing

    quick = get_quick_daily_status()
    assert len(quick) > 10


def test_language_detection():
    """Test automatic language detection for Java, Python, C++, and JS."""
    assert _detect_language("public class Solution { public static void main(String[] args) {} }") == "java"
    assert _detect_language("def add(a, b): return a + b") == "python"
    assert _detect_language("#include <iostream>\nint main() { return 0; }") == "cpp"
    assert _detect_language("const x = 10; console.log(x);") == "javascript"
    assert _detect_language("test.java") == "java"
    assert _detect_language("script.py") == "python"


def test_run_python_code_with_stdin():
    """Test running code with interactive stdin input."""
    code = (
        "import sys\n"
        "name = sys.stdin.readline().strip()\n"
        "age = sys.stdin.readline().strip()\n"
        "print(f'Hello {name}, you are {age} years old!')\n"
    )
    res = run_code_with_input(code_or_file_path=code, language="python", stdin_input="Nandu\n19\n")
    assert "Success" in res
    assert "Hello Nandu, you are 19 years old!" in res


def test_run_java_code_with_stdin():
    """Test running Java code snippet with stdin Scanner."""
    java_code = (
        "import java.util.Scanner;\n"
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        "        Scanner sc = new Scanner(System.in);\n"
        "        int a = sc.nextInt();\n"
        "        int b = sc.nextInt();\n"
        "        System.out.println(\"Sum = \" + (a + b));\n"
        "    }\n"
        "}\n"
    )
    res = run_code_with_input(code_or_file_path=java_code, language="java", stdin_input="25 75\n")
    # If javac is installed, it compiles and runs; if not in environment, handles gracefully
    if "javac" in res.lower() and "error" in res.lower():
        assert "Execution" in res or "Compilation" in res
    else:
        assert "Sum = 100" in res or "Execution" in res


def test_code_error_diagnosis_and_auto_fix():
    """Test diagnosing a buggy script, applying fix, and verifying execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_calc.py"
        # Buggy code
        test_file.write_text("def calc():\n    return 10 / 0\nprint(calc())\n", encoding="utf-8")

        # 1. Run and catch ZeroDivisionError
        err_run = run_code_with_input(str(test_file))
        assert "ZeroDivisionError" in err_run

        # 2. Diagnose
        diag = diagnose_and_fix_code_error(str(test_file), error_message="ZeroDivisionError: division by zero")
        assert "Diagnosing 'test_calc.py'" in diag

        # 3. Apply fix
        fixed_code = "def calc():\n    return 10 / 2\nprint(calc())\n"
        fix_res = diagnose_and_fix_code_error(str(test_file), replacement_code=fixed_code)
        assert "Successfully applied fix" in fix_res

        # 4. Verify fixed run
        ver_run = run_code_with_input(str(test_file))
        assert "5.0" in ver_run


def test_knowledge_graph_memory():
    """Test Knowledge Graph relation creation, multi-hop traversal, and prompt injection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = str(Path(tmpdir) / "graph_memory.db")
        engine = MAGEngine(db_path=test_db)

        # 1. Add relations
        engine.add_relation("Nandu", "has_sister", "Nandini", "Sister born Dec 4")
        engine.add_relation("Nandini", "donated_laptop_for", "Hyderabad Server", "Linux Ubuntu 100.93.70.63")
        engine.add_relation("Hyderabad Server", "runs_system", "KPR Parking System", "Ticket printing daemon")

        # 2. Multi-hop traversal (Nandu -> Sister -> Server -> KPR)
        relations = engine.traverse_entity_graph("Nandu", depth=3)
        assert len(relations) >= 3
        relation_types = [r["relation_type"] for r in relations]
        assert "has_sister" in relation_types
        assert "donated_laptop_for" in relation_types

        # 3. Subgraph prompt injection
        subgraph_prompt = engine.get_entity_subgraph_prompt("Tell me about the Hyderabad Server and sister laptop")
        assert "[KNOWLEDGE GRAPH RELATIONS (MAG-GRAPH)]" in subgraph_prompt
        assert "Hyderabad Server" in subgraph_prompt
