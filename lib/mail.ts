import "server-only";
import nodemailer from "nodemailer";

const host = process.env.SMTP_HOST;
const from = process.env.MAIL_FROM || "SoD Flow <no-reply@sod.local>";

const transport = host
  ? nodemailer.createTransport({
      host,
      port: Number(process.env.SMTP_PORT || 587),
      secure: Number(process.env.SMTP_PORT) === 465,
      auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } : undefined,
    })
  : null;

export async function sendMail(to: string, subject: string, text: string): Promise<void> {
  if (!transport) {
    if (process.env.NODE_ENV === "production") throw new Error("Chưa cấu hình SMTP_HOST");
    // Môi trường dev chưa có SMTP: in thư ra console của server
    console.info(`\n[DEV MAIL] Tới: ${to}\nTiêu đề: ${subject}\n${text}\n`);
    return;
  }
  await transport.sendMail({ from, to, subject, text });
}
