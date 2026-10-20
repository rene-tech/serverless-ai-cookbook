"""Offline default-pointer/evidence consistency; no registry or live calls."""
import html
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).parent
MANIFEST = 'sha256:bd339b8357a381e3c453d5a5132fdc89fb514ff4b9e4cd67dc3ac2c4f1f5ca4d'
CONFIG = 'sha256:abf7424b90518ebe038c4c8553bd94f9fcc00f84826d478c8063f925b694abc2'


def evidence():
    return json.loads((ROOT/'docs/evidence/native-polling-release-20261015.json').read_text())


def test_pointer_and_console_link_select_exact_published_bytes():
    # Historical receipts remain immutable; compare the current default only
    # with its own published release evidence, not the old precheck-only image.
    receipt = json.loads((ROOT/'docs/evidence/client-observation-recovery-20261020.json').read_text())
    inline = json.loads((ROOT/'docs/evidence'/receipt['base_receipt']).read_text())
    previous = json.loads((ROOT/'docs/evidence/future-image-recovery-20261017.json').read_text())
    runtime = json.loads((ROOT/'docs/evidence'/previous['runtime_receipt']).read_text())
    values = dict(re.findall(r"^(SCIENTIFIC_AI_[A-Z_]+)='([^']+)'$",
                             (ROOT/'scripts/release-image.sh').read_text(), re.M))
    assert values == {'SCIENTIFIC_AI_RELEASE_IMAGE':receipt['image'],
                      'SCIENTIFIC_AI_RELEASE_DIGEST':receipt['manifest'],
                      'SCIENTIFIC_AI_SKILLS_VERSION':receipt['skills_version']}
    assert receipt['all_scientific_workflows_qualified'] is False
    assert receipt['base_manifest'] == inline['manifest']
    assert inline['base_manifest'] == previous['manifest']
    assert previous['base_manifest'] == runtime['manifest']
    assert inline['browser']['rootless_live_response_without_reload']
    assert inline['browser']['saved_customer_reports_inline'] == 3
    assert inline['fleet']['clients_patched'] == 5
    assert inline['fleet']['loaded_skill_verified']
    assert inline['fleet']['processes_unchanged']
    assert runtime['contract'] == {
        'native_operation_ids': True,
        'upload_identity': 'upload_id',
        'paired_preview_api_and_ui_required': True,
        'request_shape': 'exact-discovered-current-tool-schema',
        'progress_schema': 'scientific-ai/progress/v1',
        'precheck_execution': 'synchronous-only',
        'precheck_async_fallback': False,
        'mcp_timeout_ms': 2400000,
    }
    bundle = json.loads((ROOT.parents[1]/'skills/scientific-ai/manifest.json').read_text())
    assert values['SCIENTIFIC_AI_SKILLS_VERSION'] == bundle['version']
    readme = (ROOT/'README.md').read_text()
    link = html.unescape(re.search(r'<a href="(https://console.nebius.com/serverless/endpoint/create\?[^"]+)"',readme)[1])
    selected = parse_qs(urlsplit(link).query)['image']
    assert selected == [receipt['image'].rsplit(':',1)[0]+'@'+receipt['manifest']]
    assert len(values['SCIENTIFIC_AI_RELEASE_IMAGE']) < 128


def test_client_recovery_release_preserves_jobs_and_running_workbenches():
    receipt = json.loads((ROOT/'docs/evidence/client-observation-recovery-20261020.json').read_text())
    installed = receipt['installed_tests']
    assert installed['consecutive_clean_cohorts'] == 2
    assert installed['tests_per_cohort'] == 166
    assert installed['skips_per_cohort'] == 0
    assert installed['source_gate_verified']
    assert installed['scientific_executor_and_ui_unchanged']
    live = receipt['live_acceptance']
    assert live['paths'] == ['installed-image-cli', 'public-immutable-download-cli']
    assert live['injected_result_read_failures_per_path'] == 5
    assert live['same_receipt_recovered']
    assert live['verified_artifacts_per_path'] == 47
    assert live['scientific_failure_reason_preserved']
    assert live['exit_codes_per_path'] == [75, 0, 1]
    assert live['scientific_submissions'] == live['remote_mutations'] == 0
    assert receipt['changes_to_running_endpoints'] == 0
    assert not receipt['provider_recreation_tested']
    assert not receipt['sustainable_capacity_measured']
    assert not receipt['all_scientific_workflows_qualified']
    guide = (ROOT/'docs/client-observation-recovery-20261020.md').read_text()
    assert f"serverless-ai-cookbook/{receipt['source']}/" in guide
    assert 'serverless-ai-cookbook/main/' not in guide


def test_image_only_release_does_not_claim_live_endpoint_replacement():
    receipt = json.loads((ROOT/'docs/evidence/future-image-recovery-20261017.json').read_text())
    assert receipt['installed_tests']['consecutive_clean_cohorts'] == 2
    assert receipt['installed_tests']['tests_per_cohort'] == 139
    assert receipt['installed_tests']['old_unfixed_image_rejected']
    assert receipt['changes_to_running_endpoints'] == receipt['scientific_submissions'] == 0
    assert not receipt['provider_recreation_tested']


def test_ui_update_does_not_claim_automatic_reloads_or_scientific_requalification():
    receipt = json.loads((ROOT/'docs/evidence/client-update-20261017.json').read_text())
    assert receipt['browser']['real_open_tab_transition']
    assert receipt['browser']['unsent_draft_preserved']
    assert receipt['browser']['reload_confirmation_cancelled_without_navigation']
    assert receipt['browser']['exact_report_visually_verified']
    assert receipt['browser']['automatic_reload'] is False
    assert receipt['browser']['new_scientific_operations'] == 0
    assert receipt['fleet']['clients_verified'] == 5
    assert receipt['fleet']['authenticated_logins_verified'] == 6
    assert receipt['fleet']['processes_unchanged']
    assert receipt['fleet']['provider_base_image_changed'] is False


def test_catalog_correction_is_live_but_not_a_blanket_workflow_qualification():
    receipt = json.loads((ROOT/'docs/evidence/catalog-contract-r2-20261017.json').read_text())
    assert receipt['inherited_ui_receipt'] == 'client-update-20261017.json'
    assert receipt['installed_catalog_tests_passed'] == 27
    assert receipt['real_chat']['passed'] and receipt['real_chat']['completed_turns'] == 2
    assert receipt['real_chat']['scientific_submissions'] == 0
    assert receipt['fleet']['clients_verified'] == 5
    assert receipt['fleet']['current_cached_processes_verified'] == 7
    assert receipt['all_scientific_workflows_qualified'] is False


def test_observer_release_keeps_exact_operations_and_frozen_science():
    receipt = json.loads((ROOT/'docs/evidence/observer-recovery-20261017.json').read_text())
    live = receipt['live_acceptance']
    assert live['scientific_operations'] == live['verified_completed_workflows'] == 2
    assert live['existing_operation_recovered'] and live['second_request_admitted_before_first_completed']
    assert live['duplicate_scientific_submissions'] == 0
    assert not live['remote_worker_disrupted']
    assert receipt['scientific_executor_bytes_unchanged']
    assert receipt['fleet']['clients_verified'] == 5
    assert receipt['fleet']['api_and_state_supervisors_preserved']
    assert not receipt['sustainable_capacity_measured']


def test_historical_precheck_evidence_preserves_its_original_scope():
    receipt = json.loads((ROOT/'docs/evidence/mdprecheck-release-20261016.json').read_text())
    foundation = json.loads((ROOT/'docs/evidence'/receipt['foundation_receipt']).read_text())
    assert receipt['base_manifest'] == foundation['manifest']
    assert receipt['installed']['persistent_entrypoint_unchanged']
    assert receipt['installed']['inherited_base_layers'] == 124
    assert receipt['installed']['additional_layers'] == 1
    assert receipt['installed']['all_core_file_hashes_verified']
    assert receipt['installed']['loaded_skills'] == 85
    assert receipt['installed']['core_files'] == 88
    assert foundation['installed']['scientific_shell']
    assert foundation['installed']['compiled_branding']
    assert foundation['installed']['synthetic_chat_guard']
    assert receipt['browser']['final_installed_runner_used']
    assert receipt['browser']['repeated_chat_reused_same_operation']
    assert receipt['browser']['authenticated_downloads_match_artifacts_and_bucket']
    assert receipt['rollout']['clients'] == 5
    assert receipt['rollout']['login_hashes_and_history_preserved']
    assert receipt['rollout']['provider_base_image_changed'] is False
    assert receipt['private_checker_source_included'] is False
    assert receipt['all_scientific_workflows_qualified'] is False


def test_current_acceptance_keeps_bounded_execution_distinct_from_capacity():
    receipt = json.loads((ROOT/'docs/evidence/current-contract-release-20261017.json').read_text())
    assert receipt['qualification_status'] == 'qualified-bounded-current-contract'
    assert receipt['sustainable_capacity_measured'] is False
    assert receipt['cross_gpu_recovery_tested'] is False
    assert receipt['all_scientific_workflows_qualified'] is False
    assert receipt['retained_fleet']['verified_clients'] == 5
    assert receipt['public_login_pages']['verified_clients'] == 4
    assert receipt['public_login_pages']['authenticated_customer_actions'] is False
    for path in ('rest', 'mcp'):
        run = receipt['live_acceptance'][path]
        assert run['completed'] and run['gpu_released']
        assert run['durable_ns'] == 0.1 and run['checkpoint_step'] == 50000
        assert run['validated_artifacts'] == 9
        assert run['same_native_id_and_result_across_rest_and_mcp']
    browser = receipt['live_acceptance']['browser']
    assert browser['completed_study_phases'] == browser['total_study_phases'] == 2
    assert browser['natural_language_request']
    assert browser['optional_precheck_offered_and_consented']
    assert browser['inline_precheck_visually_verified']
    assert browser['precheck_html_and_json_downloads_nonempty']
    assert browser['precheck_original_downloads_byte_exact']
    assert browser['inline_3d_final_structure_visually_verified']
    assert browser['customer_ui_exposes_gpu_type_or_count'] is False
    assert browser['trajectory_animation_qualified'] is False
    assert receipt['live_acceptance']['obsolete_wrapper_rejection'] == {
        'rest_status': 422, 'mcp_jsonrpc_code': -32602, 'new_jobs_admitted': 0,
    }
    assert set(receipt['evidence_sha256']) == {
        'rest_mcp_summary', 'four_retained_login_pages', 'qa_browser_acceptance',
        'obsolete_wrapper_rejections',
    }
    assert all(re.fullmatch('[0-9a-f]{64}', value)
               for value in receipt['evidence_sha256'].values())


def test_receipt_preserves_real_scope_and_unknown_provider_usage():
    receipt = evidence()
    assert receipt['manifest'] == MANIFEST and receipt['config'] == CONFIG
    assert receipt['source'] == '65b88e24ca1ed20d73b6a6c7eef0ef8366e6d21e'
    assert receipt['independent_installed']['configured_uid'] == 0
    assert receipt['independent_installed']['sdk_tests_passed'] == 20
    assert receipt['independent_installed']['sdk_tests_skipped'] == 0
    assert receipt['browser']['new_scientific_operations'] == 0
    assert receipt['browser']['installed_qa_image_unchanged'] is True
    assert receipt['browser']['original_agent_restored'] is True
    assert receipt['browser']['autonomous_skill_loading_qualified'] is False
    assert receipt['browser']['provider_requests_actual'] is None
    assert receipt['browser']['provider_cost_actual_usd'] is None
    assert receipt['customer_ready'] is receipt['all_workflows_qualified'] is False
    assert receipt['isolated_state_restore']['upload_fixtures'] == 0
    assert receipt['isolated_state_restore']['local_containers_stopped'] is True
    assert receipt['rollback_manifest'] != MANIFEST


def test_default_chat_model_and_explicit_runtime_override_are_unchanged():
    deploy = (ROOT/'scripts/deploy.sh').read_text()
    assert 'IMAGE="${IMAGE:-${SCIENTIFIC_AI_RELEASE_IMAGE%:*}@${SCIENTIFIC_AI_RELEASE_DIGEST}}"' in deploy
    assert 'SCIENTIFIC_CHAT_MODEL:-moonshotai/Kimi-K3' in deploy
    assert 'SCIENTIFIC_CHAT_MAX_OUTPUT_TOKENS:-16384' in deploy
