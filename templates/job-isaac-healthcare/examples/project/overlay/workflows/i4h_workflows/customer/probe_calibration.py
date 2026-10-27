"""Observe an ultrasound workspace with an authored scene, task and mode."""
from i4h_engine.graph import TaskGraph, task
from i4h_engine.interface import Workflow
from i4h_workflow_modes.replay import replay


def observe(seconds=5.0):
    return TaskGraph(description='Record a finite observation of the probe workspace.').flow(
        task('probe_tools/hold', seconds=float(seconds))
    )


WORKFLOW = Workflow(
    scene='probe_calibration', modes={'observe': observe, 'replay': replay},
    default_mode='observe',
)
