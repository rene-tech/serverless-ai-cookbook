// Local deterministic fixture only; imports the actual customer components.
import { useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import LiveSpeech from './LiveSpeech';
import AudioRecorder from './AudioRecorder';
function Fixture() {
  const value = useRef('Review: '); const [text, setText] = useState(value.current);
  const methods = { getValues: () => value.current, setValue: (_key: string, next: string) => { value.current = next; setText(next); } };
  return <BrowserRouter><h1>Local deterministic speech UI fixture — no model accuracy claim</h1>
    {location.pathname === '/compact' ? <><textarea aria-label="Composer" value={text} onChange={e => { value.current = e.target.value; setText(e.target.value); }} />
      <AudioRecorder disabled={false} isSubmitting={false} ask={() => { throw new Error('Never auto-send'); }} methods={methods as never} />
      <button type="button" onClick={() => { throw new Error('Fixture Send must not be clicked'); }}>Send manually</button></> : <LiveSpeech />}
  </BrowserRouter>;
}
createRoot(document.getElementById('root')!).render(<Fixture />);
