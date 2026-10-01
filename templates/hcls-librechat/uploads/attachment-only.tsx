import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { QueryKeys, request } from 'librechat-data-provider';
import type { TConversation } from 'librechat-data-provider';
import { useChatContext, useChatFormContext } from '~/Providers';
import { getAudioAttachment, subscribeAudio, submitWithWorkshopAudio } from './workshop-client';
import { getWorkspaceFiles, messageAttachedFiles, subscribeWorkspaceFiles, submitWithWorkspaceFiles } from './workspace-files';
import { saveAttachmentMessage } from './save-attachment';

/** Ordinary Send with only uploaded files persists a user message, never asks
 * an LLM. Text prompts retain the normal chat/tool-calling path. */
export default function useAttachmentOnlySend(conversation: TConversation | null) {
  const { getMessages, setMessages, setConversation } = useChatContext();
  const methods = useChatFormContext();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [, refresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const live = useRef(conversation); live.current = conversation;
  // An explicit retry after an uncertain save reuses the same native IDs.
  const transaction = useRef<{ key: string; conversationId?: string; messageId: string; importTitle: string; importAttempted?: boolean } | null>(null);
  useEffect(() => subscribeWorkspaceFiles(() => refresh(value => value + 1)), []);
  useEffect(() => subscribeAudio(() => refresh(value => value + 1)), []);
  const id = conversation?.conversationId || 'new';
  const audio = getAudioAttachment(id);
  const draft = getWorkspaceFiles(id);
  const count = (audio && !audio.sent ? 1 : 0) + (draft?.files || []).filter(file => !file.sent).length;
  const uploading = (audio && !audio.sent && audio.status === 'uploading')
    || (draft?.files || []).some(file => !file.sent && file.status === 'uploading');
  const send = async (data: { text: string }, normalSubmit: (data: { text: string }) => unknown) => {
    const prepare = (next, submit) => submitWithWorkspaceFiles(next, conversation,
      audioData => submitWithWorkshopAudio(audioData, conversation, submit));
    if (data.text?.trim() || !count) return prepare(data, normalSubmit);
    if (busy || uploading || !conversation) return false;
    setBusy(true);
    const origin = conversation;
    try {
      return await prepare({ ...data, attachmentOnly: true }, async next => {
        const files = messageAttachedFiles(next.text);
        if (!files.length) return false;
        const key = JSON.stringify([id, files.map(file => [file.workspace_path, file.sha256])]);
        if (transaction.current?.key !== key) transaction.current = { key,
          importTitle: `Upload ${crypto.randomUUID()}`, messageId: crypto.randomUUID() };
        const previous = getMessages() || [];
        const title = id === 'new' ? files[0].name : conversation.title;
        const saved = await saveAttachmentMessage(request, transaction.current, conversation, next.text, previous, title);
        const { conversationId, messageId } = saved;
        const nextConversation = { ...conversation, conversationId, title };
        queryClient.setQueryData([QueryKeys.messages, conversationId], [...previous.filter(row => row.messageId !== messageId), saved]);
        queryClient.setQueryData([QueryKeys.conversation, conversationId], nextConversation);
        void queryClient.invalidateQueries([QueryKeys.allConversations]);
        // Do not pull a user back if they changed chats while Save was pending.
        if (live.current === origin) {
          setMessages([...previous.filter(row => row.messageId !== messageId), saved]);
          setConversation(nextConversation);
          methods.reset();
          if (id === 'new') navigate(`/c/${conversationId}`, { replace: true });
        }
        return true;
      });
    } finally { setBusy(false); }
  };
  return { count, busy: busy || !!uploading, send };
}
