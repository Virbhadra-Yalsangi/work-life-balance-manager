import ast
import unittest
from pathlib import Path


class TestDashboardStructure(unittest.TestCase):
    def test_daily_bar_chart_is_created_and_rendered_only_for_nonempty_data(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        tree = ast.parse(app_path.read_text(encoding="utf-8"))

        dashboard_guard = None
        for node in tree.body:
            if isinstance(node, ast.If) and isinstance(node.test, ast.Attribute):
                if (
                    isinstance(node.test.value, ast.Name)
                    and node.test.value.id == "df"
                    and node.test.attr == "empty"
                ):
                    dashboard_guard = node
                    break

        self.assertIsNotNone(dashboard_guard, "Dashboard must handle df.empty")

        assigned_chart = any(
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "bar_chart" for target in node.targets)
            for node in ast.walk(ast.Module(body=dashboard_guard.orelse, type_ignores=[]))
        )
        rendered_chart = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
            and node.func.attr == "plotly_chart"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "bar_chart"
            for node in ast.walk(ast.Module(body=dashboard_guard.orelse, type_ignores=[]))
        )

        self.assertTrue(assigned_chart, "bar_chart must be created in the non-empty branch")
        self.assertTrue(rendered_chart, "bar_chart must be rendered in the non-empty branch")


if __name__ == "__main__":
    unittest.main()
