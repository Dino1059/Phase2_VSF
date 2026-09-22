import { Badge } from '@/components/ui/badge';
import type { PipelineStatus } from '@/lib/data/pipeline-types';
export function PipelineStatusBadge({status}:{status:PipelineStatus}){return <Badge tone={status==='SUCCESS'?'green':status==='FAILED'?'red':'amber'}>{status}</Badge>}
