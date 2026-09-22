import { Badge } from '@/components/ui/badge';
import type { FindingSeverity, FindingState } from '@/lib/data/dashboard-types';

const severityTone: Record<FindingSeverity, 'red'|'amber'|'blue'|'slate'> = { CRITICAL:'red', HIGH:'red', MEDIUM:'amber', LOW:'blue' };
const stateTone: Record<FindingState, 'red'|'blue'|'green'|'amber'> = { OPEN:'red', IN_REVIEW:'blue', REMEDIATED:'green', CLOSED:'green' };
export function SeverityBadge({value}:{value:FindingSeverity}) { return <Badge tone={severityTone[value]}>{value}</Badge>; }
export function StateBadge({value}:{value:FindingState}) { return <Badge tone={stateTone[value]}>{value.replace('_',' ')}</Badge>; }
