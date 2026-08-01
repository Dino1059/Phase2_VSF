import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Tag,
  Space,
  Typography,
  Select,
  Alert,
  Badge,
  Timeline,
  Drawer,
  Statistic,
  message,
  Tabs,
} from 'antd';
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SearchOutlined,
  FileTextOutlined,
  BugOutlined,
  ToolOutlined,
  AimOutlined,
  CompassOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { AnomalyEvent } from '../types';

const { Text, Paragraph, Title } = Typography;

const initialAnomalies: AnomalyEvent[] = [
  {
    id: 'ANO_801',
    timestamp: '2026-08-01 09:12:00',
    target_column: 'driver_pay',
    metric: 'Negative Value & Out-of-Bounds Spike',
    severity: 'Critical',
    detected_value: '-$15.00',
    expected_range: '$0.00 - $250.00',
    root_cause: 'Upstream payment microservice release v2.4 inverted refund adjustment signs into negative driver payouts.',
    remediation_suggestion: 'Apply RULE_PAY_BOUNDS_001 quarantine and auto-rectify refund offset calculation.',
    impact_summary: '15 driver compensation payouts affected. Total risk valuation: $3,420.00.',
    status: 'Open',
  },
  {
    id: 'ANO_802',
    timestamp: '2026-08-01 08:45:30',
    target_column: 'hvfhs_license_num',
    metric: 'Invalid Schema Format (Regex Match Fail)',
    severity: 'Warning',
    detected_value: '"INVALID_VEND"',
    expected_range: 'Regex ^HV[0-9]{4}$',
    root_cause: 'Legacy third-party API adapter dispatched deprecated vendor strings during surge period.',
    remediation_suggestion: 'Quarantine invalid license rows and mapping lookup for vendor translation.',
    impact_summary: '2 record batches quarantined. Downstream ETL tables isolated cleanly.',
    status: 'Investigating',
  },
  {
    id: 'ANO_803',
    timestamp: '2026-08-01 07:30:15',
    target_column: 'trip_miles',
    metric: 'Missing / Null Value Invariant Spike',
    severity: 'Info',
    detected_value: 'NULL (4.2% rate)',
    expected_range: '0.1 - 100.0 miles',
    root_cause: 'GPS telemetry packet drop on mobile client during tunnel transit.',
    remediation_suggestion: 'Apply median trip distance imputation (RULE_MILES_IMPUTE_003).',
    impact_summary: 'Low operational impact. Automatic median imputation resolves null gaps.',
    status: 'Resolved',
  },
];

export const AnomalyDiagnosis: React.FC = () => {
  const { canEditRules } = useRole();
  const [anomalies, setAnomalies] = useState<AnomalyEvent[]>(initialAnomalies);
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyEvent | null>(initialAnomalies[0]);
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  const filteredAnomalies = anomalies.filter((a) => {
    if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false;
    return true;
  });

  const handleApplyRemediation = (id: string) => {
    setAnomalies((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status: 'Resolved' } : a))
    );
    if (selectedAnomaly?.id === id) {
      setSelectedAnomaly((prev) => (prev ? { ...prev, status: 'Resolved' } : null));
    }
    message.success(`Automated remediation applied to anomaly ${id}! Status marked as Resolved.`);
  };

  const getSeverityTag = (sev: AnomalyEvent['severity']) => {
    switch (sev) {
      case 'Critical':
        return <Tag color="red" icon={<WarningOutlined />}>Critical Incident</Tag>;
      case 'Warning':
        return <Tag color="orange" icon={<ExclamationCircleOutlined />}>Warning</Tag>;
      case 'Info':
        return <Tag color="blue" icon={<CheckCircleOutlined />}>Info</Tag>;
    }
  };

  const openCount = anomalies.filter((a) => a.status === 'Open').length;
  const investigatingCount = anomalies.filter((a) => a.status === 'Investigating').length;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* Top Banner & KPI Statistics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Open Incident Alerts"
              value={openCount}
              valueStyle={{ color: openCount > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<BugOutlined style={{ color: '#ff4d4f' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Under RCA Diagnosis"
              value={investigatingCount}
              valueStyle={{ color: '#faad14' }}
              prefix={<AimOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card bodyStyle={{ padding: 16 }}>
            <Statistic
              title="Root-Cause Engine"
              value="Active (LLM + Invariant Analysis)"
              valueStyle={{ fontSize: 15 }}
              prefix={<CompassOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Grid: Timeline + Detailed RCA Panel */}
      <Row gutter={[16, 16]}>
        {/* Left Column: Timeline / Stream */}
        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <WarningOutlined style={{ color: '#faad14' }} />
                <span>Anomaly Event Stream</span>
              </Space>
            }
            extra={
              <Select
                value={severityFilter}
                onChange={setSeverityFilter}
                style={{ width: 130 }}
                options={[
                  { value: 'ALL', label: 'All Severities' },
                  { value: 'Critical', label: 'Critical' },
                  { value: 'Warning', label: 'Warning' },
                  { value: 'Info', label: 'Info' },
                ]}
              />
            }
          >
            <Timeline
              mode="left"
              items={filteredAnomalies.map((item) => ({
                color: item.severity === 'Critical' ? 'red' : item.severity === 'Warning' ? 'orange' : 'blue',
                children: (
                  <Card
                    size="small"
                    hoverable
                    style={{
                      border: selectedAnomaly?.id === item.id ? '2px solid #1890ff' : '1px solid #f0f0f0',
                      marginBottom: 8,
                      borderRadius: 6,
                    }}
                    onClick={() => setSelectedAnomaly(item)}
                  >
                    <Space direction="vertical" style={{ width: '100%' }} size={2}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        {getSeverityTag(item.severity)}
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {item.timestamp}
                        </Text>
                      </div>
                      <Text strong style={{ fontSize: 14 }}>
                        {item.target_column}: {item.metric}
                      </Text>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: 12, fontFamily: 'Fira Code' }}>
                          {item.id}
                        </Text>
                        <Badge
                          status={item.status === 'Resolved' ? 'success' : item.status === 'Open' ? 'error' : 'processing'}
                          text={item.status}
                        />
                      </div>
                    </Space>
                  </Card>
                ),
              }))}
            />
          </Card>
        </Col>

        {/* Right Column: Interactive Root-Cause Diagnosis (RCA) Deep Dive */}
        <Col xs={24} lg={14}>
          {selectedAnomaly ? (
            <Card
              title={
                <Space>
                  <BugOutlined style={{ color: '#1890ff' }} />
                  <span>Root-Cause Diagnosis & Impact Assessment: {selectedAnomaly.id}</span>
                </Space>
              }
              extra={
                canEditRules && selectedAnomaly.status !== 'Resolved' && (
                  <Button
                    type="primary"
                    icon={<ToolOutlined />}
                    onClick={() => handleApplyRemediation(selectedAnomaly.id)}
                    style={{ background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)' }}
                  >
                    Apply Automated Patch Rule
                  </Button>
                )
              }
            >
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {/* Event Summary Box */}
                <Alert
                  message={
                    <Space>
                      {getSeverityTag(selectedAnomaly.severity)}
                      <Text strong>{selectedAnomaly.target_column} Invariant Anomaly</Text>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" style={{ marginTop: 8 }}>
                      <Text>
                        <strong>Detected Value:</strong>{' '}
                        <Tag color="volcano" style={{ fontFamily: 'Fira Code' }}>
                          {selectedAnomaly.detected_value}
                        </Tag>
                      </Text>
                      <Text>
                        <strong>Expected Range / Pattern:</strong>{' '}
                        <Tag color="cyan" style={{ fontFamily: 'Fira Code' }}>
                          {selectedAnomaly.expected_range}
                        </Tag>
                      </Text>
                    </Space>
                  }
                  type={selectedAnomaly.severity === 'Critical' ? 'error' : 'warning'}
                  showIcon
                />

                {/* AI Root Cause Analysis */}
                <Card
                  type="inner"
                  title={
                    <Space>
                      <ThunderboltOutlined style={{ color: '#faad14' }} />
                      <span>AI Root Cause Analysis (RCA Rationale)</span>
                    </Space>
                  }
                  style={{ background: '#fafafa' }}
                >
                  <Paragraph style={{ fontSize: 14, color: '#262626', lineHeight: 1.6 }}>
                    {selectedAnomaly.root_cause}
                  </Paragraph>
                </Card>

                {/* Impact Analysis & Risk */}
                <Card
                  type="inner"
                  title={
                    <Space>
                      <FileTextOutlined style={{ color: '#722ed1' }} />
                      <span>Business & Technical Impact Summary</span>
                    </Space>
                  }
                >
                  <Paragraph style={{ fontSize: 13, color: '#595959' }}>
                    {selectedAnomaly.impact_summary}
                  </Paragraph>
                </Card>

                {/* Suggested Remediation Plan */}
                <Card
                  type="inner"
                  title={
                    <Space>
                      <ToolOutlined style={{ color: '#52c41a' }} />
                      <span>Recommended Active Healing Action</span>
                    </Space>
                  }
                >
                  <Paragraph style={{ fontSize: 13, color: '#262626' }}>
                    {selectedAnomaly.remediation_suggestion}
                  </Paragraph>
                </Card>
              </Space>
            </Card>
          ) : (
            <Card>
              <Text type="secondary">Select an anomaly event from the timeline to inspect root-cause diagnosis.</Text>
            </Card>
          )}
        </Col>
      </Row>
    </Space>
  );
};
