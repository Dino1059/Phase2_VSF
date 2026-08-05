import type { ChatMessage as ChatMessageType } from '../../types';
import { AgentMessage } from './AgentMessage';
import { UserMessage } from './UserMessage';
import { SystemMessage } from './SystemMessage';

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  switch (message.type) {
    case 'user':
      return <UserMessage message={message} />;
    case 'agent':
    case 'proposal':
      return <AgentMessage message={message} />;
    case 'system':
    case 'handoff':
      return <SystemMessage message={message} />;
    default:
      return null;
  }
}
