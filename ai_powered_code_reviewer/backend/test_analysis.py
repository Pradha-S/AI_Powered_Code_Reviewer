import ast
import unittest

from analysis import analyze_tree, syntax_issue
from main import AnalysisRequest, analyze_code


class AnalysisTests(unittest.TestCase):
    def analyze(self, code: str) -> list[dict[str, int | str]]:
        return analyze_tree(ast.parse(code))

    def test_syntax_error_has_line_and_actionable_description(self) -> None:
        try:
            ast.parse("def broken(:\n    pass")
        except SyntaxError as error:
            issue = syntax_issue(error)
        else:
            self.fail("Expected invalid Python to raise SyntaxError.")

        self.assertEqual(issue["line"], 1)
        self.assertIn("could not parse", issue["description"])
        self.assertTrue(issue["fix"])

    def test_analysis_endpoint_returns_syntax_finding_with_line(self) -> None:
        result = analyze_code(
            AnalysisRequest(code="def valid():\n    return 1\n    ???")
        )

        self.assertEqual(result["issues"][0]["title"], "Python syntax error")
        self.assertEqual(result["issues"][0]["line"], 3)
        self.assertIn("invalid syntax", result["error"])

    def test_analysis_score_deducts_by_severity_and_never_goes_below_zero(self) -> None:
        cases = [
            ('"""module"""\neval(source)', 75),
            ('"""module"""\nvalue is 1', 85),
            ('"""module"""\nimport os', 95),
            ('"""module"""\nimport os\neval(source)\nvalue is 1', 55),
            ('"""module"""\n' + "eval(source)\n" * 5, 0),
        ]

        for code, expected_score in cases:
            with self.subTest(expected_score=expected_score):
                result = analyze_code(AnalysisRequest(code=code))
                self.assertEqual(result["score"], expected_score)

    def test_flags_unsafe_calls_and_safe_yaml_loader_is_accepted(self) -> None:
        issues = self.analyze(
            "import yaml\n"
            "import subprocess\n"
            "eval(source)\n"
            "subprocess.run(command, shell=True)\n"
            "yaml.load(document, Loader=yaml.SafeLoader)\n"
        )

        titles = [issue["title"] for issue in issues]
        self.assertIn("Dynamic code execution", titles)
        self.assertIn("Shell execution enabled", titles)
        self.assertNotIn("Potentially unsafe YAML loading", titles)
        self.assertTrue(all(int(issue["line"]) > 0 for issue in issues))

    def test_flags_unused_local_and_import_but_not_referenced_names(self) -> None:
        issues = self.analyze(
            "import os\n"
            "import math\n"
            "print(math.pi)\n"
            "def calculate():\n"
            "    unused = 3\n"
            "    result = 4\n"
            "    return result\n"
        )

        unused = [
            issue
            for issue in issues
            if issue["title"] in {"Unused import", "Unused local variable"}
        ]
        self.assertEqual(len(unused), 2)
        self.assertEqual({issue["line"] for issue in unused}, {1, 5})
        self.assertIn("os", " ".join(str(issue["description"]) for issue in unused))
        self.assertIn("unused", " ".join(str(issue["description"]) for issue in unused))

    def test_comprehension_targets_are_not_reported_as_function_locals(self) -> None:
        issues = self.analyze(
            "def values():\n"
            "    return [0 for index in range(3)]\n"
        )

        self.assertNotIn("Unused local variable", {issue["title"] for issue in issues})

    def test_detects_bugs_quality_issues_and_reports_source_lines(self) -> None:
        issues = self.analyze(
            "def update(values=[]):\n"
            "    if values == None:\n"
            "        return 1\n"
            "        return 2\n"
            "    return 10 / 0\n"
        )

        titles = {issue["title"] for issue in issues}
        self.assertIn("Mutable default argument", titles)
        self.assertIn("Use identity comparison for None", titles)
        self.assertIn("Unreachable statement", titles)
        self.assertIn("Division by zero", titles)
        self.assertTrue(all(int(issue["line"]) > 0 for issue in issues))


if __name__ == "__main__":
    unittest.main()
