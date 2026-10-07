"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { logEvidencePdfAction } from "@/app/actions/evidence";

/** Nút In / Lưu PDF: ghi nhật ký rồi mở hộp thoại in của trình duyệt (cùng cách với phiếu). Báo cáo nằm ở `children`. */
export default function EvidencePrint({ filter, children }: { filter: Record<string, string>; children: ReactNode }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    document.body.classList.add("has-modal");
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => {
      document.body.classList.remove("has-modal");
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const print = async () => {
    await logEvidencePdfAction(filter); // ghi nhật ký trước khi in
    window.print();
  };

  return (
    <>
      <button type="button" className="btn sm" onClick={() => setOpen(true)}>In / Lưu PDF</button>
      {open &&
        createPortal(
          <div className="modal" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
            <div className="modal-card">
              <div className="modal-actions row">
                <b>Xem trước báo cáo</b>
                <span className="spacer" />
                <button type="button" className="btn primary sm" onClick={print}>In / Lưu PDF</button>
                <button type="button" className="btn sm" onClick={() => setOpen(false)}>Đóng</button>
              </div>
              <div className="modal-body">{children}</div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
