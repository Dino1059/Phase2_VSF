import type { ChatMessage as ChatMessageType } from '../../types';
import { AgentMessage } from './AgentMessage';
import { UserMessage } from './UserMessage';
import { SystemMessage } from './SystemMessage';

interface Props {
  message: ChatMessageType;
  onSelectTrace?: (tool: string) => void;
}

export function ChatMessage({ message, onSelectTrace }: Props) {
  // Thought stays out of chat (Technical detail on Traces). Used chip is on AgentMessage.
  if (message.content?.trim().startsWith('Thought:')) {
    return null;
  }

  switch (message.type) {
    case 'user':
      return <UserMessage message={message} />;
    case 'agent':
    case 'proposal':
      return <AgentMessage message={message} onSelectTrace={onSelectTrace} />;
    case 'system':
    case 'handoff':
      return <SystemMessage message={message} />;
    default:
      return null;
  }
}
