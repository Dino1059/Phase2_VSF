"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Phieu, { type PhieuProps } from "./phieu";

/**
 * Nút mở phiếu xem trước; In / Lưu PDF bằng hộp thoại in của trình duyệt.
 * Modal gắn thẳng vào <body> để CSS in (body.has-modal > .modal) chỉ in phiếu.
 */
export default function PhieuButton({ label, before, ...phieu }: PhieuProps & { label: string; before?: () => boolean }) {
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

  return (
    <>
      <button type="button" className="btn sm" onClick={() => (!before || before()) && setOpen(true)}>
        {label}
      </button>
      {open &&
        createPortal(
          <div className="modal" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
            <div className="modal-card">
              <div className="modal-actions row">
                <b>Xem trước phiếu</b>
                <span className="spacer" />
                <button type="button" className="btn primary sm" onClick={() => window.print()}>
                  In / Lưu PDF
                </button>
                <button type="button" className="btn sm" onClick={() => setOpen(false)}>
                  Đóng
                </button>
              </div>
              <div className="modal-body">
                <Phieu {...phieu} />
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
