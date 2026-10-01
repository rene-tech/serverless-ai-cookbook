// Recover one empty, normally stopped provider generation. This retries only
// the LLM invocation with its unchanged history; it never calls a tool, replays
// a command, changes models or resubmits scientific work.
'use strict';

function hasVisibleContent(content) {
  if (typeof content === 'string') return content.trim().length > 0;
  if (!Array.isArray(content)) return content != null;
  return content.some((part) => {
    if (part?.type === 'text') return String(part.text ?? '').trim().length > 0;
    if (['thinking', 'reasoning', 'reasoning_content', 'think'].includes(part?.type)) return false;
    // Unknown structured content may be a refusal, image or other deliverable.
    // Do not discard it merely because it is not a text answer.
    return part != null;
  });
}

function isEmptyStoppedResponse(result) {
  if (!Array.isArray(result?.messages) || result.messages.length !== 1) return false;
  const message = result.messages[0];
  const type = message?.getType?.() ?? message?._getType?.() ?? message?.type;
  return type === 'ai' && message.response_metadata?.finish_reason === 'stop' &&
    message.response_metadata?.preempted !== true &&
    !message.additional_kwargs?.refusal &&
    !message.tool_calls?.length && !message.invalid_tool_calls?.length &&
    !message.additional_kwargs?.tool_calls?.length &&
    !hasVisibleContent(message.content);
}

async function invokeWithRecovery({ invoke, signal, canRetry, observeEmpty }) {
  const first = await invoke();
  if (!isEmptyStoppedResponse(first) || signal?.aborted || !canRetry()) return first;
  observeEmpty(first.messages[0]);
  // Exactly one additional attempt. The existing request/context/output/step
  // ceilings, cancellation signal and provider error handling remain in force.
  const second = await invoke();
  const message = second?.messages?.[0];
  if (message) {
    message.response_metadata = { ...message.response_metadata,
      scientific_empty_response_retries: 1 };
  }
  return second;
}

module.exports = { hasVisibleContent, isEmptyStoppedResponse, invokeWithRecovery };
