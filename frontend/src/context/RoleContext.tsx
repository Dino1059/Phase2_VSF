import React, { createContext, useContext, useState, ReactNode } from 'react';
import { UserRole } from '../types';

interface RoleContextType {
  userRole: UserRole;
  setUserRole: (role: UserRole) => void;
  canEditRules: boolean;
  canManageSchedules: boolean;
  canExecuteTransforms: boolean;
  canResetSystem: boolean;
}

const RoleContext = createContext<RoleContextType | undefined>(undefined);

export const RoleProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [userRole, setUserRole] = useState<UserRole>('Admin');

  const canEditRules = userRole === 'Admin' || userRole === 'Steward';
  const canManageSchedules = userRole === 'Admin';
  const canExecuteTransforms = userRole === 'Admin' || userRole === 'Steward';
  const canResetSystem = userRole === 'Admin';

  return (
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
  );
};

export const useRole = (): RoleContextType => {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error('useRole must be used within a RoleProvider');
  }
  return context;
};
