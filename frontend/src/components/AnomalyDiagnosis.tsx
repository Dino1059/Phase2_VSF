import React, { useState, useEffect } from 'react';
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
  Spin,
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
  RadarChartOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { AnomalyEvent } from '../types';
import { apiService } from '../services/api';

const { Text, Paragraph, Title } = Typography;

const mapAlertToAnomalyEvent = (alert: any): AnomalyEvent => {
  const meta = alert.metadata || {};
  const rc = alert.root_cause || {};

  let severity: 'Critical' | 'Warning' | 'Info' = 'Info';
  const rawSev = (alert.severity || meta.severity || '').toString().toUpperCase();
  if (rawSev === 'CRITICAL' || rawSev === 'HIGH') {
    severity = 'Critical';
  } else if (rawSev === 'WARNING' || rawSev === 'MEDIUM') {
    severity = 'Warning';
  } else if (rawSev === 'INFO' || rawSev === 'LOW') {
    severity = 'Info';
  }

  let status: 'Open' | 'Investigating' | 'Resolved' = 'Open';
  const rawStatus = (alert.status || meta.status || '').toString().toUpperCase();
  if (rawStatus === 'RESOLVED') {
    status = 'Resolved';
  } else if (rawStatus === 'ACKNOWLEDGED' || rawStatus === 'INVESTIGATING') {
    status = 'Investigating';
  } else if (rawStatus === 'ACTIVE' || rawStatus === 'OPEN') {
    status = 'Open';
  }

  const target_column =
    meta.target_column || rc.affected_component || alert.target_column || alert.title || 'Unknown Column';
  const metric =
    meta.metric || rc.triggering_metric || rc.category || alert.metric || alert.message || 'Anomaly Metric';
  const detected_value =
    meta.detected_value !== undefined
      ? meta.detected_value
      : rc.current_value !== undefined
      ? rc.current_value
      : alert.detected_value !== undefined
      ? alert.detected_value
      : 'N/A';
  const expected_range =
    meta.expected_range || rc.expected_baseline || alert.expected_range || 'N/A';
  const root_cause =
    meta.root_cause ||
    rc.suspected_cause ||
    rc.summary ||
    (typeof alert.root_cause === 'string' ? alert.root_cause : alert.message) ||
    'No root cause analysis specified.';
  const remediation_suggestion =
    meta.remediation_suggestion ||
    rc.suggested_action ||
    alert.remediation_suggestion ||
    'Review data pipeline and apply automated quarantine rule.';
  const impact_summary =
    meta.impact_summary || rc.summary || alert.impact_summary || alert.message || 'Impact assessment pending.';

  return {
    id: alert.alert_id || alert.id || `ANO_${Math.floor(Math.random() * 1000)}`,
    timestamp: alert.timestamp ? new Date(alert.timestamp).toLocaleString() : new Date().toLocaleString(),
    target_column,
    metric,
    severity,
    detected_value,
    expected_range,
    root_cause,
    remediation_suggestion,
    impact_summary,
    status,
  };
};

const defaultProfileData = {
  row_count: 500,
  column_count: 7,
  duplicate_count: 12,
  columns: [
    { column_name: 'driver_pay', data_type: 'FLOAT', null_count: 5, min_val: -15.0, max_val: 450.0, mean_val: 95.54 },
    { column_name: 'hvfhs_license_num', data_type: 'VARCHAR', null_count: 0, distinct_count: 4 },
    { column_name: 'trip_miles', data_type: 'FLOAT', null_count: 21, min_val: 0.1, max_val: 120.0, mean_val: 4.8 },
  ],
};

const defaultHistoricalProfiles = [
  {
    row_count: 1000,
    column_count: 7,
    duplicate_count: 0,
    columns: [
      { column_name: 'driver_pay', data_type: 'FLOAT', null_count: 0, min_val: 5.0, max_val: 250.0, mean_val: 22.5 },
      { column_name: 'hvfhs_license_num', data_type: 'VARCHAR', null_count: 0, distinct_count: 10 },
      { column_name: 'trip_miles', data_type: 'FLOAT', null_count: 0, min_val: 0.5, max_val: 30.0, mean_val: 3.2 },
    ],
  },
];

export const AnomalyDiagnosis: React.FC = () => {
  const { canEditRules } = useRole();
  const [anomalies, setAnomalies] = useState<AnomalyEvent[]>([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyEvent | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(false);
  const [detecting, setDetecting] = useState<boolean>(false);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const rawAlerts = await apiService.getAlerts();
      const alertList = Array.isArray(rawAlerts) ? rawAlerts : [];
      const mapped = alertList.map(mapAlertToAnomalyEvent);
      setAnomalies(mapped);
      if (mapped.length > 0) {
        setSelectedAnomaly((prev) => {
          if (!prev) return mapped[0];
          const exists = mapped.find((a) => a.id === prev.id);
          return exists || mapped[0];
        });
      } else {
        setSelectedAnomaly(null);
      }
    } catch (err: any) {
      console.error('Failed to fetch alerts:', err);
      message.error(err.message || 'Failed to fetch alerts from backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const filteredAnomalies = anomalies.filter((a) => {
    if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false;
    return true;
  });

  const handleApplyRemediation = async (id: string) => {
    setLoading(true);
    try {
      await apiService.resolveAlert(id);
      message.success(`Automated remediation applied to anomaly ${id}! Status marked as Resolved.`);
      await fetchAlerts();
    } catch (err: any) {
      console.error('Failed to resolve alert:', err);
      message.error(err.message || `Failed to resolve alert ${id}.`);
      setLoading(false);
    }
  };

  const handleRunDetection = async () => {
    setDetecting(true);
    try {
      const result = await apiService.detectAnomalies({
        current_profile: defaultProfileData,
        historical_profiles: defaultHistoricalProfiles,
      });

      const detectedList = result?.all_anomalies || [];
      if (detectedList.length > 0) {
        for (const item of detectedList) {
          await apiService.createAlert({
            title: `Anomaly: ${item.column || item.metric_name || 'Metric Shift'}`,
            message: item.description || `Anomaly detected in ${item.column}`,
            severity:
              item.severity?.toUpperCase() === 'CRITICAL'
                ? 'CRITICAL'
                : item.severity?.toUpperCase() === 'HIGH'
                ? 'HIGH'
                : 'MEDIUM',
            source: 'Anomaly Detector',
            root_cause: {
              affected_component: item.column || 'dataset',
              triggering_metric: item.metric_name,
              current_value: item.current_value,
              suspected_cause: item.description,
              suggested_action: 'Apply automated quarantine rule.',
            },
            metadata: {
              target_column: item.column || 'N/A',
              metric: item.metric_name || 'Metric Shift',
              detected_value: item.current_value,
              expected_range: 'Baseline stats',
              root_cause: item.description,
              remediation_suggestion: 'Apply automated quarantine rule.',
              impact_summary: item.description,
              status: 'Open',
            },
          });
        }
        message.success(`Anomaly detection complete. ${detectedList.length} new alert(s) created!`);
      } else {
        await apiService.createAlert({
          title: 'Anomaly Scan Run',
          message: 'Anomaly detection run completed cleanly. Baseline variance within acceptable tolerance.',
          severity: 'LOW',
          source: 'Anomaly Detector',
          metadata: {
            target_column: 'system',
            metric: 'variance_check',
            detected_value: '0.0',
            expected_range: 'Within bounds',
            root_cause: 'Routine invariant check executed.',
            remediation_suggestion: 'No action required.',
            impact_summary: 'Dataset health score 100%.',
            status: 'Resolved',
          },
        });
        message.info('Anomaly detection scan complete. Baseline variance within tolerance.');
      }
      await fetchAlerts();
    } catch (err: any) {
      console.error('Failed anomaly detection:', err);
      message.error(err.message || 'Failed to run anomaly detection.');
    } finally {
      setDetecting(false);
    }
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
    <Spin spinning={loading}>
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
                <Space>
                  <Button
                    type="primary"
                    icon={<RadarChartOutlined />}
                    loading={detecting}
                    onClick={handleRunDetection}
                  >
                    Run Anomaly Detection
                  </Button>
                  <Button
                    icon={<ReloadOutlined />}
                    loading={loading}
                    onClick={fetchAlerts}
                  />
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
                </Space>
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
                      loading={loading}
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
    </Spin>
  );
};
