import React, { useState } from 'react';
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
} from 'antd';
import {
  BellOutlined,
  UserOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  AuditOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { setCurrentApiRole, apiService } from '../services/api';
import { UserRole, NotificationAlert } from '../types';

const { Header: AntHeader } = Layout;
const { Text, Title } = Typography;

const initialAlerts: NotificationAlert[] = [
  {
    id: 'alt_001',
    timestamp: new Date(Date.now() - 300000).toLocaleTimeString(),
    title: 'High Null Rate Detected',
    message: 'Column "driver_pay" null rate spiked to 12.4% in batch NYC_TLC_TRIP_082026',
    severity: 'Critical',
    read: false,
    category: 'Data Quality',
  },
  {
    id: 'alt_002',
    timestamp: new Date(Date.now() - 1200000).toLocaleTimeString(),
    title: 'Upstream Schema Drift Alert',
    message: 'New unrecognized column "vendor_fee_v2" detected in raw ingestion topic',
    severity: 'Warning',
    read: false,
    category: 'Schema Drift',
  },
  {
    id: 'alt_003',
    timestamp: new Date(Date.now() - 3600000).toLocaleTimeString(),
    title: 'Governance Rule Auto-Approved',
    message: 'Rule RULE_PAY_BOUNDS_001 passed high confidence threshold (>95%)',
    severity: 'Info',
    read: false,
    category: 'Governance',
  },
];

interface HeaderProps {
  onResetComplete?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onResetComplete }) => {
  const { userRole, setUserRole, canResetSystem } = useRole();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [alerts, setAlerts] = useState<NotificationAlert[]>(initialAlerts);
  const [activeTab, setActiveTab] = useState<string>('all');
  const [resetting, setResetting] = useState(false);

  const handleRoleChange = (newRole: UserRole) => {
    setUserRole(newRole);
    setCurrentApiRole(newRole);
    message.success(`Switched role to ${newRole} (API requests will include X-User-Role: ${newRole})`);
  };

  const unreadCount = alerts.filter((a) => !a.read).length;

  const markAllRead = () => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
    message.info('All notifications marked as read');
  };

  const markSingleRead = (id: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a)));
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
