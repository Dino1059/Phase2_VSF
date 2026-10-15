import React from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/src/stores/authStore';
import { AlertTriangle, ArrowLeft, ShieldAlert, UserCheck } from 'lucide-react';

interface AuthGuardProps {
  children: React.ReactNode;
  requiredAccess?: 'sod' | 'datatrust' | 'any';
}

export function AuthGuard({ children, requiredAccess = 'any' }: AuthGuardProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const systemAccess = useAuthStore((s) => s.systemAccess);
  const user = useAuthStore((s) => s.user);

  if (!isAuthenticated || !user) {
    const redirectUrl = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirectUrl}`} replace />;
  }

  // Kiểm tra ranh giới phân quyền (Boundary Enforcement)
  if (requiredAccess === 'sod') {
    const isAllowed = systemAccess === 'sod_only' || systemAccess === 'both';
    if (!isAllowed) {
      return (
        <div className="min-h-screen bg-[#f7faf9] flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-2xl border border-rose-200 shadow-xl p-6 text-center space-y-4">
            <div className="size-14 mx-auto rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <ShieldAlert size={28} />
            </div>
            <div className="space-y-1">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-600">403 · Ranh giới Phân quyền</span>
              <h2 className="text-lg font-bold text-slate-900">Không có quyền truy cập SoD Flow</h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                Tài khoản <span className="font-semibold text-slate-800">{user.fullName || user.username}</span> thuộc nhóm vai trò{' '}
                <span className="font-semibold text-rose-600">Chỉ DataTrust OS</span> ({user.role}). Thẩm quyền của bạn giới hạn trong việc kiểm soát chất lượng dữ liệu và không được phép truy cập phân hệ Phân tách trách nhiệm (SoD Flow).
              </p>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-left text-xs space-y-1">
              <div className="font-semibold text-slate-700">Chính sách SoD (Segregation of Duties):</div>
              <div className="text-slate-500">Người dùng chỉ được phép truy cập đúng phân hệ nghiệp vụ đã được phê duyệt trong ma trận RACIX.</div>
            </div>
            <div className="flex flex-col gap-2 pt-2">
              <button
                type="button"
                onClick={() => navigate('/overview')}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-semibold text-xs flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <ArrowLeft size={14} />
                Quay lại DataTrust OS (/overview)
              </button>
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="w-full py-2 px-4 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <UserCheck size={14} />
                Đổi Persona khác
              </button>
            </div>
          </div>
        </div>
      );
    }
  }

  if (requiredAccess === 'datatrust') {
    const isAllowed = systemAccess === 'datatrust_only' || systemAccess === 'both';
    if (!isAllowed) {
      return (
        <div className="min-h-screen bg-[#f7faf9] flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-2xl border border-amber-200 shadow-xl p-6 text-center space-y-4">
            <div className="size-14 mx-auto rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
              <AlertTriangle size={28} />
            </div>
            <div className="space-y-1">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-600">403 · Ranh giới Phân quyền</span>
              <h2 className="text-lg font-bold text-slate-900">Không có quyền truy cập DataTrust OS</h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                Tài khoản <span className="font-semibold text-slate-800">{user.fullName || user.username}</span> thuộc nhóm vai trò{' '}
                <span className="font-semibold text-amber-600">Chỉ SoD Flow</span> ({user.role}). Bạn chỉ có thẩm quyền khởi tạo hoặc phê duyệt yêu cầu cấp quyền / RBAC trong phân hệ SoD.
              </p>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-left text-xs space-y-1">
              <div className="font-semibold text-slate-700">Nguyên tắc Least Privilege:</div>
              <div className="text-slate-500">Tài khoản thuộc nhóm vận hành SoD không được phép truy cập trực tiếp vào các pipeline kiểm toán và dữ liệu nhạy cảm của DataTrust OS.</div>
            </div>
            <div className="flex flex-col gap-2 pt-2">
              <button
                type="button"
                onClick={() => navigate('/sod')}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-900 hover:bg-slate-800 text-[#04D3D4] font-semibold text-xs flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <ArrowLeft size={14} />
                Quay lại SoD Flow Workspace (/sod)
              </button>
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="w-full py-2 px-4 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <UserCheck size={14} />
                Đổi Persona khác
              </button>
            </div>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}
