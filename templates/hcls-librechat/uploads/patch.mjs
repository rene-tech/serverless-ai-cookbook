import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const replace = (source, before, after, name) => {
  if (source.split(before).length !== 2) throw new Error(`Unsupported pinned workspace-upload patch: ${name}`);
  return source.replace(before, after);
};

export function patchMenu(source) {
  for (const [before, after] of [
    ["import { cn } from '~/utils';", "import { cn } from '~/utils';\nimport { request } from 'librechat-data-provider';\nimport { selectWorkspaceFiles } from '~/components/workspace-files';"],
    ['  const inputRef = useRef<HTMLInputElement>(null);', '  const inputRef = useRef<HTMLInputElement>(null);\n  const workspaceInputRef = useRef<HTMLInputElement>(null);\n  const [workspaceUploadError, setWorkspaceUploadError] = useState(\'\');'],
    ['      const items: MenuItemProps[] = [];', `      const items: MenuItemProps[] = [{
        label: 'Upload file',
        onClick: () => { if (workspaceInputRef.current) { workspaceInputRef.current.value = ''; workspaceInputRef.current.click(); } },
        icon: <FileType2Icon className="icon-md" />,
      }];`],
    ["          label: localize('com_ui_upload_provider'),", "          label: currentProvider === Providers.GOOGLE || currentProvider === Providers.OPENROUTER ? 'Upload media to model' : 'Upload image/PDF to model',"],
    ['    <>\n      <FileUpload', `    <>
      <input ref={workspaceInputRef} type="file" multiple aria-label="Upload file to workspace" className="hidden" disabled={isUploadDisabled} onChange={(event) => {
        try { selectWorkspaceFiles(conversation, Array.from(event.target.files || []), request); setWorkspaceUploadError(''); }
        catch (error) { setWorkspaceUploadError(error instanceof Error ? error.message : 'Could not upload files.'); }
        event.target.value = '';
      }} />
      {workspaceUploadError && <span role="alert" className="text-xs text-status-error">{workspaceUploadError}</span>}
      <FileUpload`],
  ]) source = replace(source, before, after, 'AttachFileMenu');
  return source;
}

export function patchForm(source) {
  source = replace(source, "import { submitWithWorkshopAudio } from '~/components/workshop-client';",
    "import { submitWithWorkshopAudio } from '~/components/workshop-client';\nimport useAttachmentOnlySend from '~/components/attachment-only';\nimport WorkspaceAttachments from '~/components/WorkspaceAttachments';", 'ChatForm imports');
  source = replace(source, '  const submitButtonRef = useRef<HTMLButtonElement>(null);',
    '  const attachmentSend = useAttachmentOnlySend(conversation);\n  const submitButtonRef = useRef<HTMLButtonElement>(null);', 'ChatForm attachment state');
  source = replace(source, 'return submitWithWorkshopAudio(data, conversation, submitMessage);',
    'return attachmentSend.send(data, submitMessage);', 'ChatForm submit');
  source = replace(source, 'const submittableFileCount = composerReserved ? 0 : files.size;',
    'const submittableFileCount = composerReserved ? 0 : files.size + attachmentSend.count;', 'ChatForm attachment count');
  source = replace(source, '                            filesLoading ||',
    '                            filesLoading || attachmentSend.busy ||', 'ChatForm attachment busy');
  source = replace(source, '              <FileFormChat', '              <WorkspaceAttachments disabled={isSubmitting} />\n              <FileFormChat', 'ChatForm attachments');
  return source;
}

export function patchMessage(source) {
  source = replace(source, "import { visibleWorkshopPrompt } from '~/components/workshop-client';",
    "import { visibleWorkshopPrompt } from '~/components/workshop-client';\nimport { visibleWorkspacePrompt } from '~/components/workspace-files';\nimport MessageAttachments from '~/components/MessageAttachments';", 'message imports');
  source = replace(source, 'const text = isCreatedByUser ? visibleWorkshopPrompt(sourceText) : sourceText;',
    'const text = isCreatedByUser ? visibleWorkspacePrompt(visibleWorkshopPrompt(sourceText)) : sourceText;', 'message display');
  return replace(source, '</CollapsibleText>', '{isCreatedByUser && <MessageAttachments text={sourceText} />}\n    </CollapsibleText>', 'message attachments');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const [path, patch] of [
    ['/app/client/src/components/Chat/Input/Files/AttachFileMenu.tsx', patchMenu],
    ['/app/client/src/components/Chat/Input/ChatForm.tsx', patchForm],
    ['/app/client/src/components/Chat/Messages/Content/Parts/Text.tsx', patchMessage],
    ['/app/client/src/components/Chat/Messages/Content/MessageContent.tsx', patchMessage],
  ]) await writeFile(path, patch(await readFile(path, 'utf8')));
}
