# Post-consolidation workbench repair — 9 October 2026

The primary agent loads the concise `templates/hcls-librechat/agent-instructions.md`
and retrieves domain procedures through enabled skills. Two tests still searched
the obsolete inline seed manual instead of the active instructions.

The media test now verifies this loading path and the existing generative-media
skill's whole-sequence/LeRobot constraints. The study test verifies the actual
scientific-batch skill plus the published tutorial manual. That skill now
explicitly retains complete strict-JSON v2 transport, no downgrade to v1/shell on
errors, and comparison by sample identifiers rather than table shape.

Validation: the LibreChat template and skill-bundle suite passed **1,225 tests**,
with **14 skipped** and no failures. The focused media, study-transport and seeded
agent-instruction tests also passed. Skipped tests are not customer acceptance.

This is a source repair in the personal fork, integrated through the maintained
`main` workflow without a new branch. No image was built or deployed, and no
customer instance, credential or storage was changed. The guidance is included
when the next workbench image is built; existing instances are not silently
reported as updated. Historical branches remain preserved in the consolidation
archive with their prior dispositions.
