import ast
import os
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class FrozenServiceImportTests(unittest.TestCase):
    def test_every_lazy_service_is_declared_as_a_hidden_import(self):
        services_init = os.path.join(ROOT, "app", "services", "__init__.py")
        spec_path = os.path.join(ROOT, "VIUStudio.spec")

        with open(services_init, "r", encoding="utf-8") as handle:
            services_tree = ast.parse(handle.read(), filename=services_init)
        module_map = None
        for node in services_tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "_MODULE_MAP"
                for target in node.targets
            ):
                module_map = ast.literal_eval(node.value)
                break
        self.assertIsInstance(module_map, dict)

        with open(spec_path, "r", encoding="utf-8") as handle:
            spec_text = handle.read()

        missing = []
        for relative_module in module_map.values():
            concrete_module = f"services{relative_module}"
            if f'"{concrete_module}"' not in spec_text:
                missing.append(concrete_module)

        self.assertEqual(
            missing,
            [],
            "Lazy service modules missing from the PyInstaller hiddenimports: "
            + ", ".join(missing),
        )


if __name__ == "__main__":
    unittest.main()
