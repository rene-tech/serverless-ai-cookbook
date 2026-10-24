const test = require('node:test');
const assert = require('node:assert/strict');
const options = require('./scientific-tool-options.cjs');
test('current and future typed model tools are deferred after mcp_all expansion', () => {
  const value = options({ tools: ['mcp_all_mcp_scientific-ai-apps'], tool_options: {} });
  for (const name of ['cosmos3_nano_video_to_video', 'submit_cosmos3_lerobot_augmentation', 'future_typed_model']) {
    assert.equal(value[name + '_mcp_scientific-ai-apps'].defer_loading, true);
  }
  assert.equal(value.plain_helper, undefined);
  assert.equal(value['get_model_schema_mcp_scientific-ai-apps'], undefined);
  assert.equal(value['execute_command_mcp_environment-execution'], undefined);
});

test('new connected servers defer schemas without a maintained server allowlist', () => {
  const names = ['search_mcp_dropbox', 'query_mcp_cbioportal-database', 'future_mcp_new-service'];
  const value = options({ tools: ['sys__all__sys_mcp_new-service'] });
  for (const name of names) assert.equal(value[name].defer_loading, true);
  assert.equal(value['sys__all__sys_mcp_new-service'], undefined);
});

test('explicit direct or deferred selection wins and does not mutate caller settings', () => {
  const agent = { tool_options: {
    'search_mcp_dropbox': { defer_loading: false, allowed_callers: ['direct'] },
    'submit_openfold3_native_mcp_scientific-ai-apps': { defer_loading: false },
    'workbench_list_apps_mcp_scientific-demos': { defer_loading: true },
  } };
  const original = JSON.stringify(agent);
  const value = options(agent);
  for (const [name, configured] of Object.entries(agent.tool_options)) {
    assert.deepEqual(value[name], configured);
  }
  assert.equal(JSON.stringify(agent), original);
});
test('existing tool options survive unchanged except deferred schema loading', () => {
  const name = 'future_typed_model_mcp_scientific-ai-apps';
  const original = { allowed_callers: ['direct'], custom: 3 };
  const value = options({ tool_options: { [name]: original } });
  assert.deepEqual(value[name], { ...original, defer_loading: true });
  assert.deepEqual(original, { allowed_callers: ['direct'], custom: 3 });
});

test('common workbench, execution, research and viewer tools stay immediately available', () => {
  const tools = [
    { name: 'workbench_list_apps_mcp_scientific-demos' },
    { name: 'workbench_compare_structures_mcp_scientific-demos' },
    { name: 'workbench_get_operation_result_mcp_scientific-demos' },
    { name: 'execute_command_mcp_environment-execution' },
    { name: 'read_scientific_workflow_mcp_environment-execution' },
    { name: 'visualize_structure_mcp_structure-viewer' },
    { name: 'visualize_workspace_media_mcp_structure-viewer' },
    { name: 'tavily_search_mcp_tavily' },
  ];
  const value = options({ tools: tools.map((tool) => tool.name), tool_options: {} }, tools);
  for (const tool of tools) {
    assert.equal(value[tool.name], undefined, tool.name);
  }
});

test('compact App discovery stays immediately available', () => {
  const value = options({ tools: ['workbench_list_apps_mcp_scientific-demos'] });
  assert.equal(value['workbench_list_apps_mcp_scientific-demos'], undefined);
});
