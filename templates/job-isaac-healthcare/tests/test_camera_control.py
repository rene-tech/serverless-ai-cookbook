"""CPU execution of the pinned CLI/launcher/scene camera projection; no Kit/GPU."""
import argparse
import ast
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest

RECIPE = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def tree(tmp_path):
    source = os.environ.get('I4H_SOURCE')
    if not source:
        pytest.skip('I4H_SOURCE must name the pinned upstream checkout for source-projection tests')
    source = Path(source)
    patches = module('camera_patch_application', RECIPE / 'scripts/apply_runtime_patches.py')
    root, package = tmp_path / 'sdk', tmp_path / 'package'
    files = {name for patch in patches.PATCHES for name in patch['files']}
    files |= {'arena/i4h_arena/app.py', 'arena/i4h_arena/scenes/base.py',
              'arena/i4h_arena/scenes/panda_phantom.py', 'arena/i4h_arena/embodiments/franka.py'}
    for name in files:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    shutil.copytree(RECIPE / 'patches', package / 'patches')
    return root, package, patches


def extracted(source, class_name, names, namespace):
    """Execute exact upstream methods with only GPU/asset classes substituted."""
    definition = next(n for n in ast.parse(source.read_text()).body
                      if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in definition.body if isinstance(n, ast.FunctionDef) and n.name in names]
    definition.body = methods
    definition.decorator_list = []
    code = ast.Module(body=[definition], type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(source), 'exec'), namespace)
    return namespace[class_name]


@pytest.mark.parametrize('camera_choice,steps,seed,override', [
    (None, 200, 31739, False), (True, 431, 115, False),
    (False, 240, 91187, False), (False, 367, 39, True),
])
def test_actual_cli_launcher_and_scene_share_camera_intent(tree, monkeypatch, camera_choice, steps, seed, override):
    root, package, patches = tree
    patches.apply(root, package)
    cli = module('camera_test_cli', root / 'arena/i4h_arena/cli.py')
    app = module('camera_test_app', root / 'arena/i4h_arena/app.py')
    observed = {}

    def stub(name, **members):
        value = types.ModuleType(name)
        vars(value).update(members)
        monkeypatch.setitem(sys.modules, name, value)
        return value

    class EmbodimentBase:
        def __init__(self, enable_cameras, initial_pose):
            self.enable_cameras = enable_cameras

    class Empty:
        pass

    franka = extracted(root / 'arena/i4h_arena/embodiments/franka.py',
                       'FrankaUltrasoundEmbodiment', {'__init__'}, {
                           '_EmbodimentBase': EmbodimentBase, '_RobotSceneCfg': Empty,
                           '_CameraSceneCfg': Empty, '_ActionsCfg': Empty,
                           '_ObservationsCfg': lambda: types.SimpleNamespace(
                               policy=types.SimpleNamespace(wrist='camera-term', room='camera-term')),
                       })
    stub('i4h_arena.embodiments.franka', FrankaUltrasoundEmbodiment=franka)
    stub('isaaclab_arena.environments.isaaclab_arena_environment',
         IsaacLabArenaEnvironment=lambda **kw: types.SimpleNamespace(**kw))
    stub('isaaclab_arena.scene.scene', Scene=lambda **kw: kw)
    stub('i4h_arena.assets.panda_phantom', make_assets=lambda: ['unchanged-assets'])
    stub('i4h_arena.envcfg.panda_phantom', PandaPhantomEnvCfg=lambda **kw: kw)
    base = extracted(root / 'arena/i4h_arena/scenes/base.py', 'Scene', {'configure_args'},
                     {'ABC': object, 'argparse': argparse})
    scene_type = extracted(root / 'arena/i4h_arena/scenes/panda_phantom.py',
                           'PandaPhantomScene', {'build'}, {'Scene': base, 'Any': object})

    def load_scene(name, args, register_assets):
        assert name == 'ordinary-renamed-scene' and register_assets is False
        observed['at_scene_construction'] = args.enable_cameras
        scene = scene_type()
        scene.name, scene.args = name, args
        scene.spec = types.SimpleNamespace(max_steps=1200, control_hz=30.0,
                                           cameras=['room', 'wrist'], action_space='ee_pose')
        if override:
            scene.configure_args = lambda value: setattr(value, 'enable_cameras', True)
        observed['scene'] = scene
        return scene

    class Launcher:
        @staticmethod
        def add_app_launcher_args(parser):
            pass

        def __init__(self, args):
            observed['launcher_cameras'] = args.enable_cameras
            self.app = types.SimpleNamespace(close=lambda: None)

    class ProjectionComplete(Exception):
        pass

    @contextmanager
    def capture(args):
        with app.launch_app(args):
            observed['scene_env'] = observed['scene'].build()
            observed['shared_cameras'] = args.enable_cameras
        # Stop only after closing the real upstream context normally; no Kit
        # renderer, environment, simulation runner or authored workflow executes.
        raise ProjectionComplete
        yield

    stub('i4h_arena.app', launch_app=capture)
    stub('i4h_arena.scenes.base', load_scene=load_scene)
    stub('i4h_arena.medical.slang_cuda', prepare_slang_for_kit=lambda _: None)
    stub('isaaclab.app', AppLauncher=Launcher)
    monkeypatch.setattr(cli, '_check_fluoroscopy_device', lambda _: None)
    arguments = ['--workflow', 'ordinary-renamed-workflow', '--mode', 'observe',
                 '--episode-steps', str(steps), '--seed', str(seed), '--headless']
    if camera_choice is False:
        arguments.append('--no-cameras')
    args = cli.build_parser().parse_args(arguments)
    with pytest.raises(ProjectionComplete):
        cli._launch(args, types.SimpleNamespace(mode='observe', scene='ordinary-renamed-scene'))
    expected = camera_choice is not False
    assert observed['at_scene_construction'] is expected
    assert observed['shared_cameras'] is expected and observed['launcher_cameras'] is expected
    embodiment = observed['scene_env'].embodiment
    assert embodiment.enable_cameras is expected
    assert (embodiment.observation_config.policy.wrist is not None) is expected
    assert (embodiment.observation_config.policy.room is not None) is expected
    assert args.episode_steps == steps and args.seed == seed and args.mode == 'observe'
    assert observed['scene_env'].scene['assets'] == ['unchanged-assets']


def test_inherited_patch_provenance_preserved_and_mutated_source_refused(tree):
    root, package, patches = tree
    old = patches.PATCHES[0]
    before = {name: patches.sha(root / name) for name in old['files']}
    subprocess.run(['git', '-C', str(root), 'apply', str(package / 'patches' / old['patch'])], check=True)
    record = {**old, 'patch_sha256': patches.sha(package / 'patches' / old['patch']),
              'files': [{'path': name, 'source_sha256': before[name], 'sha256': patches.sha(root / name)}
                        for name in old['files']]}
    manifest = package / 'upstream-patches.json'
    manifest.write_text(json.dumps({'schema': 'isaac-healthcare-upstream-patches/v1', 'patches': [record]}))
    patches.apply(root, package)
    result = json.loads(manifest.read_bytes())
    assert result['patches'][0] == record
    assert len(result['patches']) == 2
    for row in result['patches']:
        assert patches.sha(package / 'patches' / row['patch']) == row['patch_sha256']
        assert all(patches.sha(root / file['path']) == file['sha256'] for file in row['files'])
    unchanged = manifest.read_bytes()
    patches.apply(root, package)
    assert manifest.read_bytes() == unchanged
    source = root / 'arena/i4h_arena/cli.py'
    source.write_bytes(source.read_bytes() + b'\n# unreviewed drift\n')
    with pytest.raises(ValueError, match='patched source differs'):
        patches.apply(root, package)
    assert manifest.read_bytes() == unchanged
