import React, { createContext, useContext, useState, ReactNode } from 'react';
import { UserRole } from '../types';

export type Language = 'en' | 'vi';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

interface RoleContextType {
  userRole: UserRole;
  setUserRole: (role: UserRole) => void;
  canEditRules: boolean;
  canManageSchedules: boolean;
  canExecuteTransforms: boolean;
  canResetSystem: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);
const RoleContext = createContext<RoleContextType | undefined>(undefined);

const translations: Record<Language, Record<string, string>> = {
  en: {
    appSubtitle: 'Autonomous Data Quality, Governance & Active Healing Engine',
    activeRole: 'Active Role:',
    readOnly: 'Read Only',
    incidentAlertCenter: 'Incident & Governance Alert Center',
    markAllRead: 'Mark all read',
    allNotificationsRead: 'All notifications marked as read',
    resetSystemTitle: 'Reset DataTrust System State?',
    resetSystemDesc: 'This will clear in-memory execution logs and reset the state machine.',
    resetSystemBtn: 'Reset System',
    yesReset: 'Yes, Reset',
    cancel: 'Cancel',
    tab1: 'Tab 1: Dataset Profiler & Schema',
    tab2: 'Tab 2: Rule Governance Review',
    tab3: 'Tab 3: Schedule Manager',
    tab4: 'Tab 4: Anomaly Timeline & RCA',
    tab5: 'Tab 5: Execution Results & Audit Trace',
    switchedRole: 'Switched role to',
    language: 'Language',
    all: 'All',
    unread: 'Unread',
    criticalOnly: 'Critical Only',
  },
  vi: {
    appSubtitle: 'Hệ thống AI Tự động Giám sát, Quản trị và Tự chữa lành Chất lượng Dữ liệu',
    activeRole: 'Vai trò:',
    readOnly: 'Chỉ đọc',
    incidentAlertCenter: 'Trung tâm Cảnh báo Quản trị & Sự cố',
    markAllRead: 'Đánh dấu tất cả đã đọc',
    allNotificationsRead: 'Đã đánh dấu tất cả thông báo là đã đọc',
    resetSystemTitle: 'Khôi phục Trạng thái Hệ thống DataTrust?',
    resetSystemDesc: 'Thao tác này sẽ xóa nhật ký thực thi bộ nhớ tạm và khôi phục State Machine.',
    resetSystemBtn: 'Đặt lại Hệ thống',
    yesReset: 'Đồng ý, Đặt lại',
    cancel: 'Hủy bỏ',
    tab1: 'Thẻ 1: Khảo sát Dataset & Schema',
    tab2: 'Thẻ 2: Phê duyệt Rule Governance',
    tab3: 'Thẻ 3: Quản lý Lịch chạy',
    tab4: 'Thẻ 4: Timeline Anomaly & Nguyên nhân gốc',
    tab5: 'Thẻ 5: Kết quả Thực thi & Audit Trace',
    switchedRole: 'Đã chuyển sang vai trò',
    language: 'Ngôn ngữ',
    all: 'Tất cả',
    unread: 'Chưa đọc',
    criticalOnly: 'Chỉ sự cố nghiêm trọng',
  },
};

export const AppProviders: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [userRole, setUserRole] = useState<UserRole>('Admin');
  const [language, setLanguage] = useState<Language>('vi');

  const canEditRules = userRole === 'Admin' || userRole === 'Steward';
  const canManageSchedules = userRole === 'Admin';
  const canExecuteTransforms = userRole === 'Admin' || userRole === 'Steward';
  const canResetSystem = userRole === 'Admin';

  const t = (key: string): string => {
    return translations[language]?.[key] || translations['en']?.[key] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      <RoleContext.Provider
        value={{
          userRole,
          setUserRole,
          canEditRules,
          canManageSchedules,
          canExecuteTransforms,
          canResetSystem,
        }}
      >
        {children}
      </RoleContext.Provider>
    </LanguageContext.Provider>
  );
};

export const RoleProvider = AppProviders;

export const useRole = (): RoleContextType => {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error('useRole must be used within RoleProvider');
  }
  return context;
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within RoleProvider');
  }
  return context;
};
