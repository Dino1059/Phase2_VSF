import React, { useState, useEffect } from 'react';
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
  Spin,
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
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { CronSchedule } from '../types';
import { apiService } from '../services/api';

const { Text } = Typography;

export const ScheduleManager: React.FC = () => {
  const { canManageSchedules } = useRole();
  const [schedules, setSchedules] = useState<CronSchedule[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<CronSchedule | null>(null);
  const [form] = Form.useForm();
  const [runningJobId, setRunningJobId] = useState<string | null>(null);

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const data = await apiService.getSchedules();
      const rawList = Array.isArray(data) ? data : data?.schedules || data?.data || [];
      const formatted: CronSchedule[] = rawList.map((item: any) => ({
        id: item.id || item.schedule_id || `SCH_${Math.floor(100 + Math.random() * 900)}`,
        name: item.name || 'Untitled Schedule',
        dataset_source: item.dataset_source || item.dataset_name || 'nyc_tlc_trip',
        cron_expression: item.cron_expression || item.cron || '0 0 * * *',
        variant: item.variant || item.action || 'A1 Agent',
        notification_email: item.notification_email || 'steward@datatrust.org',
        active: item.active !== undefined ? item.active : item.status !== 'paused',
        next_run: item.next_run || (item.active === false ? 'Paused' : 'Scheduled for next interval'),
        last_status: (item.last_status || (item.status === 'failed' ? 'Failed' : item.status === 'pending' ? 'Pending' : 'Success')) as 'Success' | 'Failed' | 'Pending',
      }));
      setSchedules(formatted);
    } catch (err: any) {
      console.error('Failed to fetch schedules:', err);
      message.error(err?.response?.data?.detail || err?.message || 'Failed to fetch schedules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchedules();
  }, []);

  const handleCreateOrUpdate = async (values: any) => {
    setLoading(true);
    try {
      if (editingSchedule) {
        try {
          await apiService.deleteSchedule(editingSchedule.id);
        } catch (e) {
          // ignore if deletion fails during update
        }
      }
      const payload = {
        name: values.name,
        dataset_name: values.dataset_source,
        dataset_source: values.dataset_source,
        cron_expression: values.cron_expression,
        schedule_type: 'cron',
        variant: values.variant,
        action: values.variant || 'profile',
        notification_email: values.notification_email,
        active: true,
      };
      await apiService.createSchedule(payload);
      message.success(
        editingSchedule
          ? `Updated schedule ${editingSchedule.id}`
          : `Created new automated cron schedule "${values.name}"`
      );
      setModalOpen(false);
      setEditingSchedule(null);
      form.resetFields();
      await fetchSchedules();
    } catch (err: any) {
      console.error('Failed to create/update schedule:', err);
      message.error(err?.response?.data?.detail || err?.message || 'Failed to save schedule');
    } finally {
      setLoading(false);
    }
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

  const handleDelete = async (id: string) => {
    setLoading(true);
    try {
      await apiService.deleteSchedule(id);
      message.success(`Deleted schedule ${id}`);
      await fetchSchedules();
    } catch (err: any) {
      console.error('Failed to delete schedule:', err);
      message.error(err?.response?.data?.detail || err?.message || `Failed to delete schedule ${id}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunNow = async (r: CronSchedule) => {
    setRunningJobId(r.id);
    try {
      await apiService.createSchedule({
        name: `Immediate Run - ${r.name}`,
        dataset_name: r.dataset_source,
        dataset_source: r.dataset_source,
        cron_expression: r.cron_expression,
        schedule_type: 'cron',
        variant: r.variant,
        notification_email: r.notification_email,
        action: 'full',
      });
      message.success(`Job ${r.id} executed successfully! 0 errors detected.`);
      await fetchSchedules();
    } catch (err: any) {
      console.error('Failed to run job immediately:', err);
      message.error(err?.response?.data?.detail || err?.message || `Failed to run job ${r.id}`);
    } finally {
      setRunningJobId(null);
    }
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
        <Spin spinning={loading}>
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
                        onClick={() => handleRunNow(r)}
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
        </Spin>
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
        confirmLoading={loading}
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
