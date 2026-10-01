// Exact seams in the pinned @librechat/agents 3.8.0 reliability candidate.
// Fail closed on upstream changes, before writing either installed module.
import { readFile, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

function once(source, before, after, name) {
  if (source.split(before).length !== 2 || source.includes(after)) {
    throw new Error(`Unsupported or already patched bounded-reasoning seam: ${name}`);
  }
  return source.replace(before, after);
}

export function patchGraph(source) {
  source = once(source, 'const EMPTY_PREEMPT_BOUNDARY = {',
    "const scientificBudgets = require('/opt/hcls-librechat/scientific-agent-budget.cjs');\nconst EMPTY_PREEMPT_BOUNDARY = {", 'module');
  source = once(source, '\tclearHeavyState() {\n\t\tthis.preparedSubagents.clear();',
    '\tclearHeavyState() {\n\t\tscientificBudgets.release(this);\n\t\tthis.preparedSubagents.clear();', 'cleanup');
  source = once(source, '\t\t\tconst discoveredNames = require_tools.extractToolDiscoveries(messages);',
    `\t\t\tconst scientificBudget = scientificBudgets.forRun(this);
\t\t\tconst scientificStopResponse = async (stop) => {
\t\t\t\tthis.config = config;
\t\t\t\tconst text = scientificBudgets.stopText(stop, messages);
\t\t\t\tconst key = this.getStepKey(config.metadata);
\t\t\t\t// A reasoning/text stream may already own this message identity. Append
\t\t\t\t// a text phase using it, rather than the new-message-only admission helper.
\t\t\t\tconst messageId = require_ids.getMessageId(key, this, true);
\t\t\t\tconst pauseStep = await dispatchMessageCreationStep({ graph: this, stepKey: key,
\t\t\t\t\tmessageId, content: [{ type: 'text', text }], contentType: 'text', metadata: config.metadata });
\t\t\t\tawait this.dispatchMessageDelta(pauseStep, { content: [{ type: 'text', text }] }, config.metadata);
\t\t\t\tmarkPostReasoningContent(agentContext);
\t\t\t\tconst message = new _langchain_core_messages.AIMessage({
\t\t\t\t\tid: this.messageIdsByStepKey.get(key), content: text,
\t\t\t\t\tresponse_metadata: { scientific_agent_incomplete: true, scientific_agent_stop: stop.reason }
\t\t\t\t});
\t\t\t\tthis.runProducedAiMessageIds.add(message.id);
\t\t\t\treturn { messages: [message] };
\t\t\t};
\t\t\tconst scientificPreflightStop = scientificBudget.check(messages);
\t\t\tif (scientificPreflightStop) return scientificStopResponse(scientificPreflightStop);
\t\t\tconst discoveredNames = require_tools.extractToolDiscoveries(messages);`, 'preflight');
  source = once(source, '\t\t\tconst metadata = config.metadata;\n\t\t\ttry {',
    `\t\t\tconst metadata = config.metadata;
\t\t\tconst scientificAttempt = scientificBudget.start(invokeConfig.signal);
\t\t\tinvokeConfig = { ...invokeConfig, signal: scientificAttempt.signal };
\t\t\ttry {`, 'lease');
  source = once(source,
    "result = await require('/opt/hcls-librechat/scientific-provider-recovery.cjs').invokeWithRecovery({",
    "result = await scientificAttempt.run(() => require('/opt/hcls-librechat/scientific-provider-recovery.cjs').invokeWithRecovery({", 'primary');
  source = once(source, '\t\t\t\t});\n\t\t\t} catch (primaryError) {',
    `\t\t\t\t}));
\t\t\t} catch (primaryError) {
\t\t\t\tif (scientificBudgets.isBudgetStop(primaryError)) return await scientificStopResponse(primaryError);
\t\t\t\tif (invokeConfig.signal.aborted) throw invokeConfig.signal.reason;`, 'primary stop');
  source = once(source, '\t\t\t\t\tresult = await require_langfuseRuntimeScope.withLangfuseRuntimeScope(',
    '\t\t\t\t\tresult = await scientificAttempt.run(() => require_langfuseRuntimeScope.withLangfuseRuntimeScope(', 'fallback budget');
  source = once(source, '\t\t\t\t\t}));\n\t\t\t\t} catch (fallbackError) {',
    `\t\t\t\t\t})));
\t\t\t\t} catch (fallbackError) {
\t\t\t\t\tif (scientificBudgets.isBudgetStop(fallbackError)) return await scientificStopResponse(fallbackError);
\t\t\t\t\tif (invokeConfig.signal.aborted) throw invokeConfig.signal.reason;`, 'fallback stop');
  return once(source, '\t\t\t} finally {\n\t\t\t\tawait require_langfuse.disposeLangfuseHandler(langfuseHandler);',
    '\t\t\t} finally {\n\t\t\t\tscientificAttempt.close();\n\t\t\t\tawait require_langfuse.disposeLangfuseHandler(langfuseHandler);', 'lease disposal');
}

export function patchInvoke(source) {
  return once(source, '\t\tconst throwIfBreakerTripped = () => {\n\t\t\tconst signal = config.signal;',
    `\t\tconst throwIfBreakerTripped = () => {
\t\t\tconst signal = config.signal;
\t\t\tif (signal?.aborted && require('/opt/hcls-librechat/scientific-agent-budget.cjs').isBudgetStop(signal.reason)) throw signal.reason;`,
    'late stream suppression');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const graph = '/app/node_modules/@librechat/agents/dist/cjs/graphs/Graph.cjs';
  const invoke = '/app/node_modules/@librechat/agents/dist/cjs/llm/invoke.cjs';
  const nextGraph = patchGraph(await readFile(graph, 'utf8'));
  const nextInvoke = patchInvoke(await readFile(invoke, 'utf8'));
  await writeFile(graph, nextGraph);
  await writeFile(invoke, nextInvoke);
}
