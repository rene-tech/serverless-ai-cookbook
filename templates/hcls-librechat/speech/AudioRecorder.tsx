import { memo, useRef } from 'react';
import type { TAskFunction } from '~/common';
import { useChatFormContext } from '~/Providers';
import LiveSpeech from '~/components/LiveSpeech';

// Keep the existing composer props but never auto-send clinical dictation.
// The user reviews revised partials and deliberately clicks the normal Send button.
export default memo(function AudioRecorder({ disabled, methods, isSubmitting }: {
  disabled: boolean; ask: TAskFunction; methods: ReturnType<typeof useChatFormContext>; isSubmitting: boolean;
}) {
  const original = useRef('');
  return <LiveSpeech compact disabled={disabled || isSubmitting}
    onStart={() => { original.current = methods.getValues('text') || ''; }}
    onTranscript={(text) => methods.setValue('text', [original.current, text].filter(Boolean).join(' '), { shouldValidate: true })} />;
});
