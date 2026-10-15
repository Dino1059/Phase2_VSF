"use client";

import { useRef } from "react";

/** Ô vẽ chữ ký bằng chuột / ngón tay. Trả về PNG dạng data URL, "" khi xoá. */
export default function Signature({ onChange }: { onChange: (dataUrl: string) => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);

  const ctx = () => {
    const c = ref.current!.getContext("2d")!;
    c.lineWidth = 2.2;
    c.lineCap = "round";
    c.strokeStyle = "#1a2a6c";
    return c;
  };
  const pos = (e: React.PointerEvent<HTMLCanvasElement>): [number, number] => {
    const cv = e.currentTarget;
    const r = cv.getBoundingClientRect();
    return [((e.clientX - r.left) * cv.width) / r.width, ((e.clientY - r.top) * cv.height) / r.height];
  };
  const end = () => {
    if (!drawing.current) return;
    drawing.current = false;
    onChange(ref.current!.toDataURL("image/png"));
  };

  return (
    <>
      <canvas
        ref={ref}
        className="sig"
        width={560}
        height={140}
        onPointerDown={(e) => {
          drawing.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          const c = ctx();
          c.beginPath();
          c.moveTo(...pos(e));
        }}
        onPointerMove={(e) => {
          if (!drawing.current) return;
          const c = ctx();
          c.lineTo(...pos(e));
          c.stroke();
        }}
        onPointerUp={end}
        onPointerCancel={end}
      />
      <div>
        <button
          type="button"
          className="btn sm"
          style={{ marginTop: 6 }}
          onClick={() => {
            ctx().clearRect(0, 0, 560, 140);
            onChange("");
          }}
        >
          Xoá chữ ký
        </button>
      </div>
    </>
  );
}
