import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Select,
  Badge,
  Button,
  Drawer,
  List,
  Tag,
  Space,
  Typography,
  Tooltip,
  Popconfirm,
  message,
  Tabs,
  Alert as AntAlert,
} from 'antd';
import {
  BellOutlined,
  UserOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  AuditOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { setCurrentApiRole, apiService } from '../services/api';
import { UserRole, NotificationAlert } from '../types';

const { Header: AntHeader } = Layout;
const { Text, Title } = Typography;

interface HeaderProps {
  onResetComplete?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onResetComplete }) => {
  const { userRole, setUserRole, canResetSystem } = useRole();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [alerts, setAlerts] = useState<NotificationAlert[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('all');
  const [resetting, setResetting] = useState(false);

  const fetchAlerts = useCallback(async (showLoadingState = false) => {
    if (showLoadingState) setLoading(true);
    try {
      const data = await apiService.getAlerts();
      const alertList: NotificationAlert[] = Array.isArray(data)
        ? data
        : Array.isArray(data?.alerts)
        ? data.alerts
        : Array.isArray(data?.data)
        ? data.data
        : [];
      setAlerts(alertList);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch alerts:', err);
      setError('Failed to load notifications from server');
    } finally {
      if (showLoadingState) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts(true);
    const intervalId = setInterval(() => {
      fetchAlerts(false);
    }, 30000);

    return () => clearInterval(intervalId);
  }, [fetchAlerts]);

  const handleRoleChange = (newRole: UserRole) => {
    setUserRole(newRole);
    setCurrentApiRole(newRole);
    message.success(`Switched role to ${newRole} (API requests will include X-User-Role: ${newRole})`);
  };

  const unreadCount = alerts.filter((a) => !a.read).length;

  const markAllRead = async () => {
    const unreadAlerts = alerts.filter((a) => !a.read);
    if (unreadAlerts.length === 0) return;
    try {
      await Promise.all(unreadAlerts.map((a) => apiService.acknowledgeAlert(a.id)));
      setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
      message.info('All notifications marked as read');
    } catch (err) {
      console.error('Failed to acknowledge all alerts:', err);
      message.error('Failed to mark all notifications as read');
    }
  };

  const markSingleRead = async (id: string) => {
    const alert = alerts.find((a) => a.id === id);
    if (!alert || alert.read) return;
    try {
      await apiService.acknowledgeAlert(id);
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a)));
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
      message.error('Failed to mark notification as read');
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      const res = await apiService.resetSystem();
      message.success(`System reset: ${res.message}`);
      if (onResetComplete) onResetComplete();
    } catch (e) {
      message.error('Failed to reset system');
    } finally {
      setResetting(false);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (activeTab === 'unread') return !a.read;
    if (activeTab === 'critical') return a.severity === 'Critical';
    return true;
  });

  const getSeverityTag = (sev: NotificationAlert['severity']) => {
    switch (sev) {
      case 'Critical':
        return <Tag color="error" icon={<WarningOutlined />}>Critical</Tag>;
      case 'Warning':
        return <Tag color="warning" icon={<WarningOutlined />}>Warning</Tag>;
      case 'Info':
        return <Tag color="processing" icon={<InfoCircleOutlined />}>Info</Tag>;
    }
  };

  return (
    <AntHeader
      style={{
        background: '#001529',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        height: '64px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}
    >
      {/* Brand & Logo */}
      <Space size="middle" align="center">
        <AuditOutlined style={{ fontSize: 28, color: '#1890ff' }} />
        <div>
          <Title level={4} style={{ color: '#fff', margin: 0, lineHeight: 1.2, fontWeight: 600 }}>
            DataTrust OS <Tag color="blue" style={{ marginLeft: 8 }}>v2.0</Tag>
          </Title>
          <Text style={{ color: '#8c8c8c', fontSize: 11, display: 'block' }}>
            Autonomous Data Quality, Governance & Active Healing Engine
          </Text>
        </div>
      </Space>

      {/* Right Controls: Role Switcher, Alert Bell, Reset */}
      <Space size="large" align="center">
        {/* Role Switcher */}
        <Space size="small">
          <UserOutlined style={{ color: '#aaa' }} />
          <Text style={{ color: '#ccc', fontSize: 13 }}>Active Role:</Text>
          <Select
            value={userRole}
            onChange={handleRoleChange}
            style={{ width: 130 }}
            dropdownStyle={{ borderRadius: 6 }}
            options={[
              {
                value: 'Admin',
                label: (
                  <Space>
                    <SafetyCertificateOutlined style={{ color: '#52c41a' }} />
                    <span>Admin</span>
                  </Space>
                ),
              },
              {
                value: 'Steward',
                label: (
                  <Space>
                    <AuditOutlined style={{ color: '#1890ff' }} />
                    <span>Steward</span>
                  </Space>
                ),
              },
              {
                value: 'Viewer',
                label: (
                  <Space>
                    <InfoCircleOutlined style={{ color: '#faad14' }} />
                    <span>Viewer</span>
                  </Space>
                ),
              },
            ]}
          />
          {userRole === 'Viewer' && (
            <Tag color="gold" style={{ marginLeft: 4 }}>Read Only</Tag>
          )}
        </Space>

        {/* Notification Bell */}
        <Tooltip title="Alert Center & Incident Feed">
          <Badge count={unreadCount} overflowCount={99}>
            <Button
              type="text"
              icon={<BellOutlined style={{ fontSize: 20, color: '#fff' }} />}
              onClick={() => setDrawerOpen(true)}
              style={{ borderRadius: '50%' }}
            />
          </Badge>
        </Tooltip>

        {/* System Reset Button */}
        {canResetSystem && (
          <Popconfirm
            title="Reset DataTrust System State?"
            description="This will clear in-memory execution logs and reset the state machine."
            onConfirm={handleReset}
            okText="Yes, Reset"
            cancelText="Cancel"
            okButtonProps={{ danger: true, loading: resetting }}
          >
            <Tooltip title="Reset State Machine & Audit Store">
              <Button
                type="primary"
                danger
                ghost
                icon={<ReloadOutlined spin={resetting} />}
                size="small"
              >
                Reset System
              </Button>
            </Tooltip>
          </Popconfirm>
        )}
      </Space>

      {/* Notification Alert Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <Space align="center">
              <BellOutlined style={{ color: '#1890ff' }} />
              <span>Incident & Governance Alert Center</span>
            </Space>
            {unreadCount > 0 && (
              <Button size="small" type="link" onClick={markAllRead}>
                Mark all read
              </Button>
            )}
          </div>
        }
        placement="right"
        width={420}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
      >
        {error && (
          <AntAlert
            message={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: 12 }}
          />
        )}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'all', label: `All (${alerts.length})` },
            { key: 'unread', label: `Unread (${unreadCount})` },
            { key: 'critical', label: 'Critical Only' },
          ]}
        />
        <List
          loading={loading}
          itemLayout="vertical"
          dataSource={filteredAlerts}
          renderItem={(item) => (
            <List.Item
              style={{
                backgroundColor: item.read ? '#fff' : '#e6f7ff',
                padding: '12px 16px',
                borderRadius: 8,
                marginBottom: 12,
                border: '1px solid #f0f0f0',
                cursor: 'pointer',
              }}
              onClick={() => markSingleRead(item.id)}
            >
              <Space direction="vertical" style={{ width: '100%' }} size={4}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  {getSeverityTag(item.severity)}
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {item.timestamp}
                  </Text>
                </div>
                <Text strong style={{ fontSize: 14 }}>
                  {!item.read && <Badge status="processing" style={{ marginRight: 6 }} />}
                  {item.title}
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {item.message}
                </Text>
                <Tag color="cyan" style={{ width: 'fit-content', marginTop: 4, fontSize: 11 }}>
                  {item.category}
                </Tag>
              </Space>
            </List.Item>
          )}
        />
      </Drawer>
    </AntHeader>
  );
};
