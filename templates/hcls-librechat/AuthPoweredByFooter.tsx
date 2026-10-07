import type { TStartupConfig } from 'librechat-data-provider';
import Footer from '../Chat/Footer';

export default function AuthPoweredByFooter({ startupConfig }: {
  startupConfig: TStartupConfig | null | undefined;
}) {
  return <Footer startupConfig={startupConfig ?? null}
    className="m-4 flex flex-wrap items-center justify-center gap-2 text-xs text-text-primary" />;
}
