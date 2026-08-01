import type { ChatMessage } from '../../types';

export function UserMessage({ message }: { message: ChatMessage }) {
  const time = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex justify-end">
      <div className="max-w-[80%]">
        <div className="bg-chat-user-bubble text-text-primary rounded-2xl rounded-br-md px-4 py-2.5 text-sm">
          {message.content}
        </div>
        <div className="text-[10px] text-text-muted mt-1 text-right">{time}</div>
      </div>
    </div>
  );
}
