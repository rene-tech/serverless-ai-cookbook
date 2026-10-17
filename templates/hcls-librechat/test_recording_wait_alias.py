"""Recording helpers expose an unambiguous model-operation wait option."""

from pathlib import Path

import pytest


ROOT = Path(__file__).parent


@pytest.mark.parametrize(
    "script",
    [
        "folding-comparison.py",
        "diffdock-campaign.py",
        "genmol-generate.py",
        "ct-segmentation.py",
        "ct-segmentation-batch.py",
        "cxr-analysis.py",
        "recording-batch.py",
        "proteinmpnn-design.py",
        "msa-search.py",
        "sam2-segment.py",
        "scvi-integrate.py",
        "wan-image-to-video.py",
    ],
)
def test_helper_exposes_only_current_operation_wait_option(script):
    source = (ROOT / script).read_text()
    assert "'--operation-wait-seconds', dest='wait_seconds'" in source
    assert "add_argument('--operation-wait-seconds', '--wait-seconds'" not in source
