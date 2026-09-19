import os
import sys
import io
import json
import zipfile
import tempfile
import unittest

from lens_verifier import LensVerifier

class TestLensJSLinter(unittest.TestCase):
    def setUp(self):
        self.base_lens_data = {
            "asset_statuses": {
                "prefetched_assets": {
                    "visor_3d": {"status": "SUCCESS"}
                }
            },
            "blocks": [
                {"name": "Attachment", "key": "hud_visor", "description": "3D Visor"}
            ]
        }

    def _create_bundle(self, files: dict) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for fname, content in files.items():
                z.writestr(fname, content)
        return buf.getvalue()

    def test_case_1_valid_js_script(self):
        """Test Case 1: 100% Valid JS script with no banned globals or syntax errors."""
        script_content = """
        // Clean Lens Studio script
        script.createEvent("OnStartEvent").bind(function() {
            var speed = 1.0;
            var pos = new vec3(0, 1.0, 0);
            print("Lens initialized successfully at speed: " + speed);
        });

        script.face_events = {
            onMouthOpened: function() {
                var angle = Math.sin(0.5);
                return angle;
            }
        };
        """
        # Test unit check
        ok_syntax, syntax_msg = LensVerifier.check_js_syntax(script_content)
        self.assertTrue(ok_syntax, f"Valid script failed syntax check: {syntax_msg}")
        self.assertEqual(syntax_msg, "")

        global_errs = LensVerifier.lint_js_globals("LensController.js", script_content)
        self.assertEqual(global_errs, [], f"Valid script had unexpected global errors: {global_errs}")

        # Test bundle integration
        bundle = self._create_bundle({
            "scripts/LensController.js": script_content,
            "scene.scn": "Component.RenderMeshVisual Component.Head"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "valid prompt", "lens_name": "Valid Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertTrue(passed, f"Gate 5 should pass valid script. Errors: {verifier.report['errors']}")

    def test_case_2_undeclared_tween(self):
        """Test Case 2: Script with undeclared TWEEN.Easing (reproduces Neon Synapse Visor rejection)."""
        script_content = """
        // Script replicating Neon Synapse Visor bug
        script.createEvent("OnStartEvent").bind(function() {
            var target = { x: 10 };
            // Undeclared TWEEN reference without declaration or global.TWEEN
            TWEEN.Easing.Cubic.Out(0.5);
        });
        """
        # Node -c syntax passes because syntax is valid JS, but runtime throws ReferenceError
        ok_syntax, _ = LensVerifier.check_js_syntax(script_content)
        self.assertTrue(ok_syntax, "Syntax should be valid JS")

        global_errs = LensVerifier.lint_js_globals("LensController.js", script_content)
        self.assertTrue(any("Undeclared TWEEN" in err for err in global_errs), f"Expected undeclared TWEEN error, got: {global_errs}")

        # Test bundle integration
        bundle = self._create_bundle({
            "scripts/LensController.js": script_content,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Neon Synapse Visor"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT script with undeclared TWEEN")
        self.assertTrue(any("Undeclared TWEEN" in err for err in verifier.report["errors"]))

        # Test controller_code in lens_data with undeclared TWEEN
        lens_data_with_tween = dict(self.base_lens_data)
        lens_data_with_tween["controller_code"] = script_content
        verifier2 = LensVerifier(lens_data=lens_data_with_tween, plan={"prompt": "test prompt", "lens_name": "Neon Synapse Visor"})
        clean_bundle = self._create_bundle({
            "scripts/CleanController.js": "script.createEvent('OnStartEvent');",
            "scene.scn": "Component.RenderMeshVisual"
        })
        passed2 = verifier2.verify_controller_and_assets(clean_bundle)
        self.assertFalse(passed2, "Gate 5 MUST REJECT undeclared TWEEN inside lens_data.controller_code")

    def test_case_3_canvas_api_violation(self):
        """Test Case 3: Script with CanvasAPI / createOnScreenCanvas (2D disco loading wheel)."""
        script_content = """
        // 2D canvas procedural drawing routine
        var canvas = CanvasAPI.createOnScreenCanvas();
        canvas.drawBarsHalo();
        canvas.line(0, 0, 100, 100);
        """
        # Test unit check
        global_errs = LensVerifier.lint_js_globals("CanvasController.js", script_content)
        # Should be caught by canvas_patterns in verify_controller_and_assets
        bundle = self._create_bundle({
            "scripts/CanvasController.js": script_content,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Canvas Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT script using CanvasAPI")
        g5_rep = verifier.report["gates"]["gate5_assets_and_controller"]
        self.assertTrue(g5_rep["canvas_api_detected"])
        self.assertTrue(len(g5_rep["canvas_violations"]) > 0)

    def test_case_4_syntax_error(self):
        """Test Case 4: Script with invalid JavaScript syntax (node -c failure)."""
        broken_script = """
        function brokenSyntax( {
            const x = ;
            return ;
        }
        """
        ok_syntax, syntax_msg = LensVerifier.check_js_syntax(broken_script)
        self.assertFalse(ok_syntax, "Syntax check must fail on broken JS")
        self.assertIn("SyntaxError", syntax_msg)

        bundle = self._create_bundle({
            "scripts/BrokenScript.js": broken_script,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Broken Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT script with syntax error")
        self.assertTrue(any("Syntax Error" in err for err in verifier.report["errors"]))

    def test_case_5_browser_dom_globals(self):
        """Test Case 5: Script referencing prohibited browser DOM globals (window, document, localStorage, fetch)."""
        dom_script = """
        script.createEvent("OnStartEvent").bind(function() {
            window.location = "https://example.com";
            document.getElementById("btn");
            localStorage.setItem("key", "value");
            fetch("https://api.example.com");
        });
        """
        global_errs = LensVerifier.lint_js_globals("DomScript.js", dom_script)
        self.assertTrue(any("window" in err for err in global_errs))
        self.assertTrue(any("document" in err for err in global_errs))
        self.assertTrue(any("localStorage" in err for err in global_errs))
        self.assertTrue(any("fetch" in err for err in global_errs))

        bundle = self._create_bundle({
            "scripts/DomScript.js": dom_script,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "DOM Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT scripts referencing browser DOM globals")

    def test_case_6_node_globals_and_unbundled_require(self):
        """Test Case 6: Script referencing Node process.env or unbundled require."""
        node_script = """
        const apiKey = process.env.API_KEY;
        const fs = require('fs');
        """
        global_errs = LensVerifier.lint_js_globals("NodeScript.js", node_script)
        self.assertTrue(any("process.env" in err for err in global_errs))
        self.assertTrue(any("Unbundled require('fs')" in err for err in global_errs))

        bundle = self._create_bundle({
            "scripts/NodeScript.js": node_script,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Node Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT scripts with Node globals and unbundled require")

    def test_case_7_asset_integrity_missing_asset(self):
        """Test Case 7: Script referencing non-existent asset filename."""
        script_with_missing_asset = """
        script.createEvent("OnStartEvent").bind(function() {
            var texturePath = "textures/non_existent_shockwave.png";
            var meshPath = "meshes/missing_titanium_visor.glb";
        });
        """
        bundle = self._create_bundle({
            "scripts/LensController.js": script_with_missing_asset,
            "scene.scn": "Component.RenderMeshVisual"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Asset Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertFalse(passed, "Gate 5 MUST REJECT bundle with missing referenced assets")
        g5_rep = verifier.report["gates"]["gate5_assets_and_controller"]
        self.assertTrue(g5_rep["missing_assets_count"] > 0)
        self.assertTrue(any("Missing referenced asset" in err for err in verifier.report["errors"]))

    def test_case_8_asset_integrity_present_assets(self):
        """Test Case 8: Script referencing existing assets in archive."""
        script_with_existing_asset = """
        script.createEvent("OnStartEvent").bind(function() {
            var texturePath = "textures/shockwave.png";
            var meshPath = "meshes/visor.glb";
        });
        """
        bundle = self._create_bundle({
            "scripts/LensController.js": script_with_existing_asset,
            "scene.scn": "Component.RenderMeshVisual",
            "textures/shockwave.png": b"\x89PNG\r\n\x1a\nFakePNGData",
            "meshes/visor.glb": b"glTFfakebinarydata"
        })
        verifier = LensVerifier(lens_data=self.base_lens_data, plan={"prompt": "test prompt", "lens_name": "Valid Asset Lens"})
        passed = verifier.verify_controller_and_assets(bundle)
        self.assertTrue(passed, f"Gate 5 should pass when all referenced assets exist. Errors: {verifier.report['errors']}")
        g5_rep = verifier.report["gates"]["gate5_assets_and_controller"]
        self.assertEqual(g5_rep["missing_assets_count"], 0)

if __name__ == "__main__":
    unittest.main()
