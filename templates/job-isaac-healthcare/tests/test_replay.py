"""CPU sequence/control proof; the simulator episode body is not exercised here."""

import json
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np

from isaac_healthcare_runtime.contract import parameters
from isaac_healthcare_runtime.replay import install_sequence
from isaac_healthcare_runtime.runtime import interactive_command


def recording(path):
    from i4h_common.episode import write_initial_state
    from i4h_engine.loader import resolve_workflow

    workflow = resolve_workflow('scissor_pick_and_place', 'replay', dataset=str(path), episode=0)
    with h5py.File(path, 'w') as handle:
        data = handle.create_group('data')
        data.attrs['scene'] = workflow.scene
        for index in range(2):
            demo = data.create_group(f'demo_{index}')
            demo.create_dataset('actions', data=np.full((3, 6), index, dtype=np.float32))
            write_initial_state(demo, {'marker': np.array([index])})


def drive_cli(tmp_path, monkeypatch, *, stop_after=None):
    from i4h_arena import cli, runner
    from i4h_engine.status import WorkflowStatus
    from i4h_tasks.basic.replay.replay import Replay

    dataset = tmp_path / 'unseen-recording.hdf5'
    recording(dataset)
    base = runner.SimulationRunner
    seen, applications, summaries = [], [], []

    def episode(self, engine, index, attempt):
        node = self.workflow.graph.nodes[0]
        source_index = node.params['episode']
        actions = Replay(**node.params)._load()
        assert int(self.initial_state['marker'][0]) == source_index
        assert np.all(actions == source_index)
        assert engine.graph is self.workflow.graph
        assert engine.max_steps == 450
        seen.append((source_index, index, attempt))
        status = WorkflowStatus.FAILED if index == 2 and attempt == 1 else WorkflowStatus.SUCCEEDED
        return runner.EpisodeResult(index=index, attempt=attempt, status=status, steps=3)

    monkeypatch.setattr(base, '_run_episode', episode)

    def launch(args, workflow):
        app = SimpleNamespace(is_running=lambda: stop_after is None or len(seen) < stop_after)
        applications.append(app)
        scene = SimpleNamespace(spec=SimpleNamespace(max_steps=600), make_view=lambda env: object())
        instance = runner.SimulationRunner(
            scene=scene, workflow=workflow, env=object(), app=app,
            episodes=args.episodes, attempts=args.attempts, max_steps=args.episode_steps,
            seed=args.seed, initial_state=cli._replay_initial_state(args, workflow))
        summary = instance.run()
        summaries.append(summary)
        return 0 if summary.complete else 1

    monkeypatch.setattr(cli, '_launch', launch)
    install_sequence(cli)
    output = tmp_path / 'demos.hdf5'
    code = cli.main(['--workflow', 'scissor_pick_and_place', '--mode', 'replay',
                     '--dataset', str(dataset), '--episode', '1,0', '--episodes', '2',
                     '--attempts', '2', '--episode-steps', '450', '--seed', '37',
                     '--record', str(output), '--no-cameras', '--headless'])
    assert runner.SimulationRunner is base
    assert runner._ACTIVE_RUNNER is None
    assert len(applications) == 1
    proof = json.loads(output.with_name('replay-sequence.json').read_text())
    return code, seen, summaries[0], proof


def test_actual_cli_loader_and_upstream_episode_loop_honor_all_indices_and_retries(tmp_path, monkeypatch):
    code, seen, summary, proof = drive_cli(tmp_path, monkeypatch)
    assert code == 0
    assert seen == [(1, 0, 1), (1, 1, 1), (0, 2, 1), (0, 2, 2), (0, 3, 1)]
    assert summary.requested == 4 and summary.succeeded == 4
    assert proof['requested_source_episodes'] == [1, 0]
    assert proof['repetitions_per_source_episode'] == 2
    assert proof['task_complete'] is True
    assert proof['attempts'][2]['succeeded'] is False


def test_early_app_close_preserves_unfinished_sequence_status(tmp_path, monkeypatch):
    code, seen, summary, proof = drive_cli(tmp_path, monkeypatch, stop_after=2)
    assert code == 1
    assert seen == [(1, 0, 1), (1, 1, 1)]
    assert summary.requested == 4 and summary.succeeded == 2
    assert proof['task_complete'] is False
    assert len(proof['attempts']) == 2


def test_interactive_resolved_default_replay_keeps_all_requested_indices(tmp_path):
    values = parameters({'workflow': 'authored', 'dataset': 'recordings.hdf5',
                         'replay_episodes': [9, 2], 'episode_steps': 1750, 'physics': 'newton'})
    context = {'effective_root': str(tmp_path), 'project_dir': str(tmp_path),
               'python_paths': [], 'asset_root': None}
    selected = {'mode': 'replay', 'lint': {'ok': True}, 'backends': []}
    with interactive_command(values, {'name': 'session', 'seed': 73}, tmp_path / 'session',
                             context=context, selected=selected) as (argv, env):
        assert argv[argv.index('--mode') + 1] == 'replay'
        assert argv[argv.index('--episode') + 1] == '9,2'
        assert argv[argv.index('--episode-steps') + 1] == '1750'
        assert argv[argv.index('--presets') + 1] == 'newton'
        assert '--headless' not in argv
