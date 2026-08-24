import React, { useState } from 'react';
import { RotateCcw, AlertTriangle, Loader } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ResetDbButtonProps {
  onReset: () => Promise<void>;
}

export const ResetDbButton: React.FC<ResetDbButtonProps> = ({ onReset }) => {
  const { i18n } = useTranslation();
  const isVi = i18n.language === 'vi';
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleReset = async () => {
    setLoading(true);
    try {
      await onReset();
    } finally {
      setLoading(false);
      setConfirmOpen(false);
    }
  };

  return (
    <>
      <button
        className="reset-db-btn"
        onClick={() => setConfirmOpen(true)}
        title={isVi ? 'Đặt lại DB về trạng thái ban đầu (0 dòng)' : 'Reset DB to fresh initial state (0 rows)'}
      >
        <RotateCcw size={13} />
        {isVi ? 'Đặt lại DB' : 'Reset DB'}
      </button>

      {confirmOpen && (
        <div className="modal-overlay" onClick={() => setConfirmOpen(false)}>
          <div className="modal-box reset-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon">
              <AlertTriangle size={28} color="var(--warning-amber)" />
            </div>
            <h3 className="modal-title">
              {isVi ? 'Xác nhận đặt lại DB?' : 'Confirm DB Reset?'}
            </h3>
            <p className="modal-body">
              {isVi
                ? 'Thao tác này sẽ xóa quarantine, clean, batch_run_log và đặt lại các bảng raw dữ liệu về 0 dòng để sẵn sàng nạp từ Parquet theo từng ngày. File Parquet gốc trên ổ đĩa KHÔNG bị ảnh hưởng.'
                : 'This will clear quarantine, clean, batch_run_log and reset raw data tables to 0 rows for fresh day ingestion from Parquet. The original Parquet file on disk will NOT be affected.'}
            </p>
            <div className="modal-actions">
              <button
                className="modal-btn cancel"
                onClick={() => setConfirmOpen(false)}
                disabled={loading}
              >
                {isVi ? 'Hủy' : 'Cancel'}
              </button>
              <button
                className="modal-btn confirm"
                onClick={handleReset}
                disabled={loading}
              >
                {loading ? (
                  <Loader size={13} className="spin" />
                ) : (
                  <RotateCcw size={13} />
                )}
                {isVi ? 'Đặt lại' : 'Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
