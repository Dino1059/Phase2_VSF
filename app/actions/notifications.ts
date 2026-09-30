"use server";

// Chỉ đọc / đánh dấu thông báo của người đang đăng nhập.
import * as z from "zod";
import { requireUser } from "@/lib/auth/session";
import { listNotifications, markRead, syncSlaNotifications, type NotificationList } from "@/lib/notify/service";

export async function fetchNotifications(): Promise<NotificationList> {
  const user = await requireUser();
  await syncSlaNotifications(user.id);
  return listNotifications(user.id);
}

export async function markNotificationRead(id: string): Promise<void> {
  const user = await requireUser();
  if (z.uuid().safeParse(id).success) await markRead(user.id, id);
}

export async function markAllNotificationsRead(): Promise<void> {
  const user = await requireUser();
  await markRead(user.id);
}
