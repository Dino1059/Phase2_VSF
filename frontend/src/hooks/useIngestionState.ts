import { useEffect } from 'react';
import { useIngestionStore, IngestionStateStore } from '../stores/ingestionStore';
export type { IngestionStateStore as IngestionState, E2EStage, RealtimeTick, RealtimeSample } from '../stores/ingestionStore';

export function useIngestionState(): IngestionStateStore {
  const store = useIngestionStore();

  useEffect(() => {
    const cleanup = store.initWebSocketAndPolling();
    return cleanup;
  }, []);

  return store;
}
