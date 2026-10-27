"""Dependency declarations are not shader compilation or resource availability."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/mdl_dependencies.py"
SPEC = importlib.util.spec_from_file_location("mdl_dependencies", SOURCE)
MDL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MDL)
URL = "https://assets.example/public/materials/metal/main.mdl"
BUILTINS = {name + ".mdl": {"path": "/installed/mdl/" + name + ".mdl", "sha256": "a" * 64}
            for name in ("anno", "tex", "OmniPBR", "nvidia/core_definitions")}


class MDLDependencies(unittest.TestCase):
    def extract(self, text, **kwargs):
        return MDL.extract_dependencies(text, source_url=URL,
                                        builtin_material_provenance=BUILTINS, **kwargs)

    def test_comments_are_not_imports_or_files(self):
        result = self.extract('''mdl 1.7;
        // import ::missing::thing; texture_2d("./comment.png");
        /* using .::Absent import *; texture_2d("./also-comment.jpg"); */
        material m = material();''')
        self.assertEqual(result["required"], [])
        self.assertEqual(result["optional"], [])
        self.assertEqual(result["literals"], [])

    def test_all_resource_constructors_named_arguments_and_escapes(self):
        result = self.extract(r'''mdl 1.10;
        texture_2d a = texture_2d(name: "./tex\u0020one.png", gamma: tex::gamma_linear, selector: "channel.png");
        texture_3d b = texture_3d("../volume.exr");
        texture_cube c = texture_cube("./cube.dds");
        texture_ptex d = texture_ptex("./mesh.ptx");
        light_profile l = light_profile("./lamp.ies");
        bsdf_measurement s = bsdf_measurement("./cloth.mbsdf");''')
        self.assertEqual(len(result["required"]), 6)
        self.assertEqual(result["mdl_version"], [1, 10])
        first = result["required"][0]
        self.assertEqual(first["reference"], "./tex one.png")
        self.assertEqual(first["url"], URL.rsplit("/", 1)[0] + "/tex%20one.png")
        self.assertIn(r"\u0020", first["raw"])
        self.assertEqual(result["required"][1]["url"], "https://assets.example/public/materials/volume.exr")

    def test_adjacent_literals_return_constructor_and_udim_are_preserved(self):
        result = self.extract('''mdl 1.6;
        texture_2d f() { return texture_2d("./textures/" "skin.<UDIM>.png"); }''')
        self.assertEqual(result["required"][0]["reference"], "./textures/skin.<UDIM>.png")
        self.assertTrue(result["required"][0]["pattern"])
        self.assertEqual(len(result["required"]), 1)

    def test_thumbnail_optional_and_annotation_description_is_metadata(self):
        result = self.extract('''mdl 1.6;
        import ::anno::*;
        export material m() [[anno::thumbnail("./preview.png"),
          anno::description("https://documentation.example/not-a-resource.png")]] = material();''')
        self.assertEqual(result["required"], [])
        self.assertEqual(len(result["optional"]), 1)
        self.assertEqual(result["optional"][0]["kind"], "thumbnail")
        self.assertEqual(len(result["builtins"]), 1)

    def test_exact_relative_module_paths_do_not_guess_library_roots(self):
        result = self.extract('''mdl 1.6;
        using .::Helper import *;
        import ..::shared::Material::build;''')
        self.assertEqual([r["url"] for r in result["required"]], [
            "https://assets.example/public/materials/metal/Helper.mdl",
            "https://assets.example/public/materials/shared/Material.mdl"])
        with self.assertRaisesRegex(MDL.MDLDependencyError, "explicit module URL"):
            self.extract('mdl 1.6; import ::Library::Material::build;')
        mapped = self.extract('mdl 1.6; import ::Library::Material::build;',
                              module_urls={"::Library::Material": "https://library.example/pinned/Material.mdl"})
        self.assertEqual(mapped["required"][0]["resolution"], "explicit-module-mapping")

    def test_builtin_requires_hash_provenance_and_never_shadows_relative_import(self):
        result = self.extract('mdl 1.6; using ::OmniPBR import OmniPBR; import ::nvidia::core_definitions::*;')
        self.assertEqual(len(result["builtins"]), 2)
        with self.assertRaisesRegex(MDL.MDLDependencyError, "path/SHA256"):
            MDL.extract_dependencies('mdl 1.6; import ::OmniPBR::*;', source_url=URL,
                                     builtin_material_provenance={"OmniPBR.mdl": {"path": "/installed/OmniPBR.mdl"}})
        relative = self.extract('mdl 1.6; using .::OmniPBR import *;')
        self.assertEqual(relative["builtins"], [])
        self.assertEqual(relative["required"][0]["url"], URL.rsplit("/", 1)[0] + "/OmniPBR.mdl")

    def test_search_root_and_pre16_weak_relative_paths_need_explicit_resolution(self):
        with self.assertRaisesRegex(MDL.MDLDependencyError, "explicit search root"):
            self.extract('mdl 1.6; texture_2d a = texture_2d("/shared/a.png");')
        mapped = self.extract('mdl 1.6; texture_2d a = texture_2d("/shared/a.png");',
                              resource_root_url="https://cdn.example/exact-root/")
        self.assertEqual(mapped["required"][0]["url"], "https://cdn.example/exact-root/shared/a.png")
        with self.assertRaisesRegex(MDL.MDLDependencyError, "Pre-1.6 weak relative"):
            self.extract('mdl 1.5; texture_2d a = texture_2d("a.png");')
        self.assertEqual(self.extract('mdl 1.6; texture_2d a = texture_2d("a.png");')["required"][0]["url"],
                         URL.rsplit("/", 1)[0] + "/a.png")

    def test_empty_resources_are_not_files_and_nested_unknown_path_is_not_hidden(self):
        self.assertEqual(self.extract('mdl 1.6; texture_2d a = texture_2d();')["required"], [])
        with self.assertRaisesRegex(MDL.MDLDependencyError, "Unclassified external-looking"):
            self.extract('mdl 1.6; texture_2d a = texture_2d("./a.png", custom("./hidden.png"));')

    def test_string_contents_are_never_lexical_punctuation_or_keywords(self):
        result = self.extract('''mdl 1.6;
        string names[] = {"import", "using", "(", ")", ",", "mdl 1.10;", "not /*hello*/"};
        texture_2d a = texture_2d("./comma,texture.png");''')
        self.assertEqual(result["mdl_version"], [1, 6])
        self.assertEqual(len(result["required"]), 1)
        self.assertEqual(len(result["literals"]), 8)

    def test_nested_and_unclassified_annotations_do_not_hide_paths(self):
        for body in ('anno::description(custom("./hidden.png"))',
                     'anno::unclassified("./hidden.png")'):
            with self.subTest(body=body), self.assertRaisesRegex(MDL.MDLDependencyError, "Unclassified external-looking"):
                self.extract('mdl 1.6; material m() [[' + body + ']] = material();')

    def test_relative_resource_url_escapes_delimiters_without_changing_literal(self):
        result = self.extract('mdl 1.6; texture_2d a = texture_2d("./tex #1?.png");')
        self.assertEqual(result["required"][0]["reference"], "./tex #1?.png")
        self.assertEqual(result["required"][0]["url"], URL.rsplit("/", 1)[0] + "/tex%20%231%3F.png")

    def test_unknown_external_calls_and_dynamic_names_fail_closed(self):
        for text in ('unknown("./missing.exr")', 'texture_2d(name: selected_path)',
                     'texture_2d("./a.png" + selected_suffix)'):
            with self.subTest(text=text), self.assertRaises(MDL.MDLDependencyError):
                self.extract('mdl 1.6; material m = ' + text + ';')

    def test_unterminated_or_ambiguous_input_fails(self):
        for text in ('mdl 1.6; /* unclosed', 'mdl 1.6; texture_2d("unclosed)',
                     'mdl 1.6; texture_2d("./a.png";',
                     r'mdl 1.6; texture_2d("C:\\material\\a.png");',
                     r'mdl 1.6; texture_2d("./bad\q.png");'):
            with self.subTest(text=text), self.assertRaises(MDL.MDLDependencyError):
                self.extract(text)


if __name__ == "__main__":
    unittest.main()
