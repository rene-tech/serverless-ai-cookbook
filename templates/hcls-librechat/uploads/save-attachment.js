/** Use only native authenticated conversation persistence APIs, not chat/LLM.
 * New chats use the existing import route because message-save intentionally
 * rejects writes to conversations that do not exist yet. */
export async function saveAttachmentMessage(request, transaction, conversation, text, previous, title) {
  transaction.text ??= text;
  text = transaction.text;
  const userMessage = { messageId: transaction.messageId,
    parentMessageId: previous.at(-1)?.messageId || '00000000-0000-0000-0000-000000000000',
    text, isCreatedByUser: true, sender: 'User', endpoint: conversation.endpoint,
    model: conversation.model, isTemporary: false, createdAt: new Date().toISOString() };
  if (conversation.conversationId === 'new' || !conversation.conversationId) {
    if (!transaction.importAttempted) {
      // Never automatically repeat an import with an uncertain outcome.
      transaction.importAttempted = true;
      const body = new FormData();
      body.append('file', new Blob([JSON.stringify({ conversationId: transaction.messageId,
        title: transaction.importTitle, endpoint: conversation.endpoint, options: conversation,
        messages: [userMessage] })], { type: 'application/json' }), 'attachment-message.json');
      await request.postMultiPart('/api/convos/import', body);
    }
    if (!transaction.conversationId) {
      const listing = await request.get('/api/convos?limit=100');
      const matches = listing.conversations.filter(row => row.title === transaction.importTitle);
      if (matches.length !== 1) throw new Error('Could not locate the saved attachment. Reopen chat history before trying again.');
      transaction.conversationId = matches[0].conversationId;
    }
    const conversationId = transaction.conversationId;
    const messages = await request.get(`/api/messages/${conversationId}`);
    const saved = (Array.isArray(messages) ? messages : messages.messages).find(row => row.isCreatedByUser && row.text === text);
    if (!saved) throw new Error('Could not verify the saved attachment.');
    await request.post('/api/convos/update', { arg: { conversationId, title } });
    return saved;
  }
  const saved = await request.post(`/api/messages/${conversation.conversationId}`, {
    ...userMessage, conversationId: conversation.conversationId,
  });
  if (saved.messageId !== transaction.messageId || saved.conversationId !== conversation.conversationId) throw new Error('Could not verify the saved attachment message.');
  return saved;
}
