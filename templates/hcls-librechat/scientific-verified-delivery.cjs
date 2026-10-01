// Only an explicit finish tool may bypass paraphrasing. Intermediate tools,
// failures, concurrent calls and later user messages never end the workflow.
const { isHostBudgetNotice } = require('./scientific-study-admission.cjs');
const finishTools = new Set(['deliver_scientific_results_mcp_environment-execution',
  'inspect_mmcif_inventory_mcp_environment-execution']);
const messageType = (message) => message?.getType?.() ?? message?._getType?.();

module.exports = function verifiedDelivery(messages) {
  if (!Array.isArray(messages) || messages.length < 2) return null;
  const end = messages.length - (isHostBudgetNotice(messages.at(-1)) ? 1 : 0);
  const result = messages[end - 1];
  const request = messages[end - 2];
  if (messageType(result) !== 'tool' || messageType(request) !== 'ai' ||
      !finishTools.has(result.name) || result.status === 'error') return null;
  const calls = request.tool_calls;
  if (!Array.isArray(calls) || calls.length !== 1 || calls[0].name !== result.name ||
      !calls[0].id || calls[0].id !== result.tool_call_id) return null;
  if (result.name === 'inspect_mmcif_inventory_mcp_environment-execution' &&
      calls[0].args?.finish_request !== true) return null;
  let content = result.content;
  if (Array.isArray(content)) {
    if (content.length !== 1 || content[0]?.type !== 'text') return null;
    content = content[0].text;
  }
  if (typeof content !== 'string') return null;
  let receipt;
  try { receipt = JSON.parse(content); } catch { return null; }
  if (receipt?.schema !== 'scientific-verified-delivery/v1' || receipt.status !== 'completed' ||
      receipt.inference_submitted !== false || receipt.isError || receipt.error ||
      !Number.isInteger(receipt.result_count) || receipt.result_count < 1 ||
      typeof receipt.report_markdown !== 'string' || !receipt.report_markdown.trim()) return null;
  return receipt.report_markdown;
};
