"""Source composition checks; live qualification is recorded separately."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_full_builder_retains_the_verified_reporter_and_inline_ui():
    source = (ROOT / 'Dockerfile').read_text()
    assert 'COPY templates/hcls-librechat/native_md_preview.py /opt/bionemo/native_md_preview.py' in source
    for name in ('WorkspaceReportPreview.tsx', 'WorkspaceMarkdownLinks.ts', 'ScientificStudyPreview.tsx'):
        assert f'templates/hcls-librechat/{name}' in source
    assert source.index('RUN node /tmp/patch-report-preview.mjs') < source.index('/vite build')


def test_patch_image_contains_the_matching_executor_schema_and_reporter():
    source = (ROOT / 'Dockerfile.gromacs-workflow').read_text()
    for name in ('execution-mcp.py', 'scientific_study_schema.py', 'native_md_preview.py'):
        assert f'COPY templates/hcls-librechat/{name} /opt/bionemo/{name}' in source
    assert 'ScientificStudyPreview.test.tsx' in source
    assert "assert 'native-files.json' in known_output_files" in source
