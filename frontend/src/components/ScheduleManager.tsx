import React, { useState } from 'react';
import {
  Card,
  Table,
  Button,
  Tag,
  Space,
  Typography,
  Switch,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  Tooltip,
  Badge,
  Row,
  Col,
  Statistic,
  message,
} from 'antd';
import {
  ClockCircleOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  MailOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { CronSchedule } from '../types';

const { Text, Paragraph, Title } = Typography;

const initialSchedules: CronSchedule[] = [
  {
    id: 'SCH_001',
    name: 'NYC TLC Daily Governance Sweep',
    dataset_source: 'nyc_tlc_trip',
    cron_expression: '0 0 * * *',
    variant: 'A1 Agent',
    notification_email: 'steward@datatrust.org',
    active: true,
    next_run: 'Tonight at 00:00 UTC',
    last_status: 'Success',
  },
  {
    id: 'SCH_002',
    name: 'FinTech Hourly Fraud & Bounds Scan',
    dataset_source: 'fintech_transactions',
    cron_expression: '0 * * * *',
    variant: 'C1 Baseline',
    notification_email: 'secops@fintech.io',
    active: true,
    next_run: 'In 24 minutes',
    last_status: 'Success',
  },
  {
    id: 'SCH_003',
    name: 'Customer Stream Schema Invariant Check',
    dataset_source: 'customer_stream',
    cron_expression: '*/15 * * * *',
    variant: 'A1 Agent',
    notification_email: 'dev@ecommerce.com',
    active: false,
    next_run: 'Paused',
    last_status: 'Pending',
  },
];

export const ScheduleManager: React.FC = () => {
  const { canManageSchedules } = useRole();
  const [schedules, setSchedules] = useState<CronSchedule[]>(initialSchedules);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<CronSchedule | null>(null);
  const [form] = Form.useForm();
  const [runningJobId, setRunningJobId] = useState<string | null>(null);

  const handleCreateOrUpdate = (values: any) => {
    if (editingSchedule) {
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === editingSchedule.id
            ? {
                ...s,
                name: values.name,
                dataset_source: values.dataset_source,
                cron_expression: values.cron_expression,
                variant: values.variant,
                notification_email: values.notification_email,
              }
            : s
        )
      );
      message.success(`Updated schedule ${editingSchedule.id}`);
    } else {
      const newSched: CronSchedule = {
        id: `SCH_${Math.floor(100 + Math.random() * 900)}`,
        name: values.name,
        dataset_source: values.dataset_source,
        cron_expression: values.cron_expression,
        variant: values.variant,
        notification_email: values.notification_email,
        active: true,
        next_run: 'Scheduled for next interval',
        last_status: 'Pending',
      };
      setSchedules((prev) => [newSched, ...prev]);
      message.success(`Created new automated cron schedule "${values.name}"`);
    }
    setModalOpen(false);
    setEditingSchedule(null);
    form.resetFields();
  };

  const handleToggleActive = (id: string, active: boolean) => {
    setSchedules((prev) =>
      prev.map((s) =>
        s.id === id
          ? {
              ...s,
              active,
              next_run: active ? 'Scheduled for next interval' : 'Paused',
            }
          : s
      )
    );
    message.info(`Schedule ${id} ${active ? 'enabled' : 'paused'}`);
  };

  const handleDelete = (id: string) => {
    setSchedules((prev) => prev.filter((s) => s.id !== id));
    message.success(`Deleted schedule ${id}`);
  };

  const handleRunNow = (id: string) => {
    setRunningJobId(id);
    message.loading(`Executing scheduled job ${id} manually...`, 1.5);
    setTimeout(() => {
      setSchedules((prev) =>
        prev.map((s) => (s.id === id ? { ...s, last_status: 'Success' } : s))
      );
      setRunningJobId(null);
      message.success(`Job ${id} executed successfully! 0 errors detected.`);
    }, 1500);
  };

  const handlePresetSelect = (preset: string) => {
    form.setFieldsValue({ cron_expression: preset });
  };

  const openEditModal = (sched: CronSchedule) => {
    setEditingSchedule(sched);
    form.setFieldsValue({
      name: sched.name,
      dataset_source: sched.dataset_source,
      cron_expression: sched.cron_expression,
      variant: sched.variant,
      notification_email: sched.notification_email,
    });
    setModalOpen(true);
  };

  const activeCount = schedules.filter((s) => s.active).length;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* Top Banner & Metrics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Total Automated Jobs"
              value={schedules.length}
              prefix={<ClockCircleOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Active Schedules"
              value={activeCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Execution Frequency"
              value="Continuous / Cron"
              valueStyle={{ fontSize: 16 }}
              prefix={<CalendarOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Schedule Table */}
      <Card
        title={
          <Space>
            <ClockCircleOutlined style={{ color: '#1890ff' }} />
            <span>Autonomous Schedule & Recurring Governance Manager</span>
          </Space>
        }
        extra={
          canManageSchedules ? (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingSchedule(null);
                form.resetFields();
                setModalOpen(true);
              }}
            >
              Create New Schedule
            </Button>
          ) : (
            <Tag color="gold">Role Restricted (Admin Only)</Tag>
          )
        }
      >
        <Table
          dataSource={schedules}
          rowKey="id"
          pagination={false}
          columns={[
            {
              title: 'Job Name & ID',
              key: 'job_name',
              render: (_: any, r: CronSchedule) => (
                <Space direction="vertical" size={2}>
                  <Text strong>{r.name}</Text>
                  <Text type="secondary" style={{ fontSize: 11, fontFamily: 'Fira Code' }}>
                    {r.id}
                  </Text>
                </Space>
              ),
            },
            {
              title: 'Dataset Source',
              dataIndex: 'dataset_source',
              key: 'dataset_source',
              render: (ds: string) => <Tag color="blue">{ds}</Tag>,
            },
            {
              title: 'Cron Expression',
              dataIndex: 'cron_expression',
              key: 'cron_expression',
              render: (cron: string) => (
                <Tag color="purple" style={{ fontFamily: 'Fira Code' }}>
                  {cron}
                </Tag>
              ),
            },
            {
              title: 'Engine Variant',
              dataIndex: 'variant',
              key: 'variant',
              render: (v: string) => <Tag color="geekblue">{v}</Tag>,
            },
            {
              title: 'Notifications',
              dataIndex: 'notification_email',
              key: 'notification_email',
              render: (email: string) => (
                <Space size={4}>
                  <MailOutlined style={{ color: '#8c8c8c' }} />
                  <Text style={{ fontSize: 12 }}>{email}</Text>
                </Space>
              ),
            },
            {
              title: 'Status',
              key: 'active_status',
              render: (_: any, r: CronSchedule) => (
                <Space direction="vertical" size={4}>
                  <Switch
                    checked={r.active}
                    disabled={!canManageSchedules}
                    onChange={(checked) => handleToggleActive(r.id, checked)}
                    checkedChildren="Active"
                    unCheckedChildren="Paused"
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {r.next_run}
                  </Text>
                </Space>
              ),
            },
            {
              title: 'Last Execution',
              dataIndex: 'last_status',
              key: 'last_status',
              render: (st: string) => (
                <Badge
                  status={st === 'Success' ? 'success' : st === 'Failed' ? 'error' : 'default'}
                  text={st}
                />
              ),
            },
            {
              title: 'Actions',
              key: 'actions',
              render: (_: any, r: CronSchedule) => (
                <Space size="small">
                  <Tooltip title="Run Immediately">
                    <Button
                      type="primary"
                      ghost
                      icon={<PlayCircleOutlined spin={runningJobId === r.id} />}
                      size="small"
                      disabled={runningJobId === r.id || !canManageSchedules}
                      onClick={() => handleRunNow(r.id)}
                    />
                  </Tooltip>
                  {canManageSchedules && (
                    <>
                      <Tooltip title="Edit Schedule">
                        <Button
                          type="default"
                          icon={<EditOutlined />}
                          size="small"
                          onClick={() => openEditModal(r)}
                        />
                      </Tooltip>
                      <Popconfirm
                        title="Delete Schedule?"
                        onConfirm={() => handleDelete(r.id)}
                      >
                        <Button danger ghost icon={<DeleteOutlined />} size="small" />
                      </Popconfirm>
                    </>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      {/* Modal for Creating / Editing Cron Schedule */}
      <Modal
        title={editingSchedule ? `Edit Schedule: ${editingSchedule.name}` : 'Create New Autonomous Schedule'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditingSchedule(null);
        }}
        onOk={() => form.submit()}
        width={540}
      >
        <Form form={form} layout="vertical" onFinish={handleCreateOrUpdate}>
          <Form.Item name="name" label="Schedule / Job Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. Daily TLC Data Audit Sweep" />
          </Form.Item>

          <Form.Item name="dataset_source" label="Target Dataset Source" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'nyc_tlc_trip', label: '🚕 NYC TLC Trip Records Sample' },
                { value: 'fintech_transactions', label: '💳 FinTech High-Frequency Payments' },
                { value: 'customer_stream', label: '👤 E-Commerce Customer Profile Stream' },
              ]}
            />
          </Form.Item>

          <Form.Item label="Cron Expression Builder">
            <Space style={{ marginBottom: 8 }} wrap>
              <Button size="small" onClick={() => handlePresetSelect('*/15 * * * *')}>
                Every 15m
              </Button>
              <Button size="small" onClick={() => handlePresetSelect('0 * * * *')}>
                Hourly
              </Button>
              <Button size="small" onClick={() => handlePresetSelect('0 0 * * *')}>
                Daily Midnight
              </Button>
              <Button size="small" onClick={() => handlePresetSelect('0 0 * * 0')}>
                Weekly Sunday
              </Button>
            </Space>
            <Form.Item name="cron_expression" noStyle rules={[{ required: true }]}>
              <Input placeholder="e.g. 0 0 * * *" style={{ fontFamily: 'Fira Code' }} />
            </Form.Item>
          </Form.Item>

          <Form.Item name="variant" label="Execution Variant" initialValue="A1 Agent">
            <Select
              options={[
                { value: 'A1 Agent', label: '🤖 A1 Agent (Autonomous LLM + Tool Repair)' },
                { value: 'C0 Baseline', label: '⚡ C0 Baseline (Deterministic)' },
                { value: 'C1 Baseline', label: '🧠 C1 Baseline (Heuristic)' },
              ]}
            />
          </Form.Item>

          <Form.Item name="notification_email" label="Notification Recipient Email">
            <Input placeholder="governance-team@company.com" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
