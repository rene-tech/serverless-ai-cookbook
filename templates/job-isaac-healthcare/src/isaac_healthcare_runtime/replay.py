"""Replay every requested recording index in one upstream Kit/runner lifetime."""

import copy
import json
from pathlib import Path

from .contract import digest


def sequence_runner(base, plans, *, provenance_path, dataset_sha256):
    """Keep upstream run/reset/step/attempt behavior; change the per-index graph."""
    from i4h_engine.executor import Engine

    class ReplaySequenceRunner(base):
        def __init__(self, *args, **kwargs):
            self._repetitions = kwargs.get('episodes', 1)
            kwargs['episodes'] = self._repetitions * len(plans)
            super().__init__(*args, **kwargs)
            self._sequence_slot = None
            self._sequence_engine = None
            self._sequence_attempts = []

        def _run_episode(self, engine, episode, attempt):
            slot = episode // self._repetitions
            plan = plans[slot]
            if slot != self._sequence_slot:
                self.workflow = plan['workflow']
                self.initial_state = plan['initial_state']
                self.max_steps = self._requested_max_steps or self.workflow.max_steps or self.scene.spec.max_steps
                if self.recorder is not None:
                    self.recorder.workflow = self.workflow
                self._sequence_engine = Engine(
                    self.workflow.graph, workflow_name=self.workflow.name,
                    on_event=self._on_event, max_steps=self._engine_max_steps())
                self._sequence_slot = slot
            record = {'output_episode': episode, 'source_episode': plan['source_episode'],
                      'attempt': attempt, 'initial_state_present': self.initial_state is not None,
                      'status': 'started'}
            self._sequence_attempts.append(record)
            print(json.dumps({'replay_source_episode': plan['source_episode'],
                              'output_episode': episode, 'attempt': attempt}), flush=True)
            result = super()._run_episode(self._sequence_engine, episode, attempt)
            record.update({'status': result.status.name, 'steps': result.steps,
                           'succeeded': result.succeeded, 'saved_demo': result.saved_demo})
            return result

        def run(self):
            summary = None
            try:
                summary = super().run()
                return summary
            finally:
                proof = {'schema': 'isaac-healthcare-replay-sequence/v1',
                         'source_dataset_sha256': dataset_sha256,
                         'requested_source_episodes': [plan['source_episode'] for plan in plans],
                         'repetitions_per_source_episode': self._repetitions,
                         'requested_output_episodes': self.episodes,
                         'attempts': self._sequence_attempts,
                         'upstream_run_completed': summary is not None,
                         'task_complete': summary.complete if summary is not None else False,
                         'successful_episodes': summary.succeeded if summary is not None else None}
                Path(provenance_path).write_text(json.dumps(proof, indent=2) + '\n')

    return ReplaySequenceRunner


def install_sequence(cli):
    """Adapt the pinned CLI's first-index-only behavior at its normal launch seam."""
    original_launch = cli._launch

    def launch(args, workflow):
        if workflow.mode != 'replay':
            return original_launch(args, workflow)
        indices = [int(value) for value in str(args.episode).split(',')]
        if len(indices) <= 1:
            return original_launch(args, workflow)
        from i4h_arena import runner
        from i4h_arena.recording.scene_state import load_initial_state
        from i4h_engine import loader
        from i4h_engine.lint import lint_workflow
        from i4h_engine.registry import default_registry

        plans = []
        for index in indices:
            selected = copy.copy(args)
            selected.episode = str(index)
            selected.mode = 'replay'
            resolved = cli._build(selected, loader.resolve_workflow)
            loader.apply_overrides(resolved.graph, checkpoint=args.checkpoint,
                                   prompt=args.prompt, model_device=args.device)
            lint = lint_workflow(resolved, default_registry())
            if not lint.ok:
                raise ValueError(f'Replay episode {index} workflow lint failed: {lint.render()}')
            if (resolved.name, resolved.scene, resolved.mode) != (workflow.name, workflow.scene, workflow.mode):
                raise ValueError('Replay sequence changed its authored workflow/scene/mode identity')
            plans.append({'source_episode': index, 'workflow': resolved,
                          'initial_state': load_initial_state(args.dataset, index, resolved.scene)})
        if args.record is None:
            raise ValueError('Replay sequence needs its normal recording output path')
        original_runner = runner.SimulationRunner
        runner.SimulationRunner = sequence_runner(
            original_runner, plans, provenance_path=Path(args.record).with_name('replay-sequence.json'),
            dataset_sha256=digest(Path(args.dataset)))
        try:
            return original_launch(args, plans[0]['workflow'])
        finally:
            runner.SimulationRunner = original_runner

    cli._launch = launch
