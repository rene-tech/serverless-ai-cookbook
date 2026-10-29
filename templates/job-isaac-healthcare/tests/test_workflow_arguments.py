"""Pinned CLI builders honor authored overrides without replacing outer inputs."""

import json
import sys
from pathlib import Path

import pytest

from isaac_healthcare_runtime.arguments import merge_workflow_arguments
from isaac_healthcare_runtime.contract import parameters
from isaac_healthcare_runtime.inspection import resolve


def test_omitted_mode_preserves_idle_instead_of_implying_an_automatic_task(tmp_path):
    from isaac_healthcare_runtime.runtime import command

    values = parameters({'workflow': 'scissor_pick_and_place'})
    workflow = resolve(values)
    assert workflow.mode == 'idle'
    assert len(workflow.graph.nodes) == 1
    assert workflow.graph.nodes[0].task_id == 'local/idle'
    assert '--mode' not in command(values, {'seed': None}, tmp_path)


@pytest.mark.parametrize('mode', ['rule-based', 'idle', 'teleop'])
def test_explicit_demo_or_customer_mode_reaches_the_same_workflow_unchanged(tmp_path, mode):
    from isaac_healthcare_runtime.runtime import command

    values = parameters({'workflow': 'scissor_pick_and_place', 'mode': mode})
    workflow = resolve(values)
    argv = command(values, {'seed': None}, tmp_path)
    assert workflow.mode == mode and workflow.name == values['workflow']
    assert argv[argv.index('--mode') + 1] == mode
    assert argv[argv.index('--workflow') + 1] == values['workflow']
    if mode == 'rule-based':
        assert len(workflow.graph.nodes) > 1


def test_actual_teleop_builder_accepts_explicit_defaults_override_and_custom_kwargs():
    values = parameters({'workflow': 'scissor_pick_and_place', 'mode': 'teleop',
                         'workflow_args': {'port': 47041, 'sensitivity': 0.37, 'base_height': 1.4,
                                           'recalibrate': True, 'custom_device_option': 'authored'}})
    workflow = resolve(values)
    actual = workflow.graph.nodes[0].params
    for key, value in values['workflow_args'].items():
        assert actual[key] == value
    assert actual['device'] == 'keyboard'


def test_actual_teleop_builder_without_overrides_preserves_upstream_defaults():
    from i4h_arena.cli import _build, build_parser
    from i4h_engine.loader import resolve_workflow

    arguments = build_parser().parse_args(['--workflow', 'scissor_pick_and_place', '--mode', 'teleop'])
    expected = _build(arguments, resolve_workflow)
    observed = resolve(parameters({'workflow': 'scissor_pick_and_place', 'mode': 'teleop'}))
    assert observed.graph.nodes[0].params == expected.graph.nodes[0].params


@pytest.mark.parametrize('mode,outer,supplied,owner', [
    ('replay', {'dataset': 'recording.hdf5'}, {'dataset': 'different.hdf5'}, 'dataset'),
    ('replay', {'dataset': 'recording.hdf5', 'replay_episodes': [3]}, {'episode': 0}, 'replay_episodes'),
    ('idle', {'idle_seconds': 17}, {'seconds': 4}, 'idle_seconds'),
])
def test_actual_mode_builder_rejects_conflicting_outer_control(mode, outer, supplied, owner):
    values = parameters({'workflow': 'scissor_pick_and_place', 'mode': mode,
                         'workflow_args': supplied, **outer})
    with pytest.raises(ValueError, match='parameters.' + owner):
        resolve(values)


def test_actual_launch_cli_uses_same_merge_and_preserves_physics_paths_and_duration(tmp_path, monkeypatch):
    from i4h_arena import cli
    from i4h_engine import loader
    from isaac_healthcare_runtime import launch

    values = parameters({'workflow': 'scissor_pick_and_place', 'mode': 'teleop',
                         'physics': 'physx', 'episode_steps': 450,
                         'workflow_args': {'port': 47043, 'sensitivity': 0.29}})
    context = tmp_path / 'context.json'
    context.write_text(json.dumps({'project': {'effective_root': '/opt/i4h',
        'project_dir': str(tmp_path), 'python_paths': [], 'asset_root': None}, 'parameters': values}))
    seen = []

    def launch_without_simulation(args, workflow):
        seen.append((args, workflow))
        return 0

    monkeypatch.setattr(cli, '_launch', launch_without_simulation)
    monkeypatch.setattr(loader, 'resolve_workflow', loader.resolve_workflow)
    monkeypatch.setattr(sys, 'argv', ['portable-launch', '--context', str(context), '--workflow',
        'scissor_pick_and_place', '--mode', 'teleop', '--presets', 'physx', '--episode-steps', '450',
        '--record', str(tmp_path / 'recording.hdf5'), '--headless', '--no-cameras'])
    assert launch.main() == 0
    args, workflow = seen[0]
    assert args.presets == 'physx' and args.episode_steps == 450
    assert Path(args.record) == tmp_path / 'recording.hdf5'
    assert workflow.graph.nodes[0].params['port'] == 47043
    assert workflow.graph.nodes[0].params['sensitivity'] == 0.29


def test_arbitrary_builder_values_and_json_object_type_boundary():
    assert merge_workflow_arguments({'custom': 2}, {'custom': 7, 'new': {'authored': True}}) == {
        'custom': 7, 'new': {'authored': True}}
    with pytest.raises(TypeError, match='JSON objects'):
        merge_workflow_arguments({}, ['not-an-object'])
