import { formatSaigonTime } from '../../demo/stewardLabels';
import type { ChatMessage } from '../../types';

function safeFormatTime(timestamp?: string) {
  return formatSaigonTime(timestamp || null);
}

export function UserMessage({ message }: { message: ChatMessage }) {
  const time = safeFormatTime(message.timestamp);

  return (
    <div className="flex justify-end" data-msgid={message.id}>
      <div className="max-w-[80%]">
        <div className="bg-chat-user-bubble text-text-primary rounded-2xl rounded-br-md px-4 py-2.5 text-sm">
          {message.content}
        </div>
        <div className="text-[10px] text-text-muted mt-1 text-right">{time}</div>
      </div>
    </div>
  );
}
