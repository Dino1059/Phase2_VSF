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
        title={isVi ? 'Đặt lại trạng thái demo (không xóa raw data)' : 'Reset demo state (keeps raw data)'}
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
                ? 'Thao tác này sẽ xóa quarantine, batch_run_log và đặt lại demo_state về -1. Dữ liệu raw được giữ nguyên.'
                : 'This will clear quarantine, batch_run_log and reset demo_state to -1. Raw data will be preserved.'}
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
