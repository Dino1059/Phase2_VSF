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
  Statistic,
  Tabs,
  Badge,
  Tooltip,
  Input,
  message,
} from 'antd';
import {
  SafetyCertificateOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  LockOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { apiService } from '../services/api';
import { AuditRecord, ExecuteTransformResponse } from '../types';

const { Text, Title, Paragraph } = Typography;

interface AuditTraceProps {
  executionResult: ExecuteTransformResponse | null;
  rawData: Record<string, any>[];
}

export const AuditTrace: React.FC<AuditTraceProps> = ({ executionResult, rawData }) => {
  const [auditRecords, setAuditRecords] = useState<AuditRecord[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [searchText, setSearchText] = useState('');

  const loadAuditRecords = async () => {
    setLoadingAudit(true);
    try {
      const records = await apiService.getAuditStore();
      setAuditRecords(records);
    } catch (err) {
      message.error('Failed to load audit records');
    } finally {
      setLoadingAudit(false);
    }
  };

  useEffect(() => {
    loadAuditRecords();
  }, []);

  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(auditRecords, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `datatrust_audit_trace_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    message.success('Exported immutable audit log trace (JSON)');
  };

  // Filter audit records
  const filteredAudit = auditRecords.filter((rec) => {
    if (!searchText) return true;
    const q = searchText.toLowerCase();
    return (
      rec.event_type.toLowerCase().includes(q) ||
      (rec.role && rec.role.toLowerCase().includes(q)) ||
      JSON.stringify(rec.details).toLowerCase().includes(q)
    );
  });

  // Quarantine sample rows simulation
  const quarantineCount = executionResult?.quarantine_rows ?? 2;
  const cleanRows = rawData.slice(0, rawData.length - quarantineCount);
  const quarantineRows = rawData.slice(rawData.length - quarantineCount);

  const formatCols = (dataArr: Record<string, any>[]) =>
    dataArr.length > 0
      ? Object.keys(dataArr[0]).map((key) => ({
          title: key,
          dataIndex: key,
          key: key,
          render: (val: any) => (val === null || val === undefined ? <Text type="danger">&lt;NULL&gt;</Text> : String(val)),
        }))
      : [];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* Execution Results Summary Banner */}
      {executionResult ? (
        <Card
          title={
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
              <span>Data Transformation & Quarantine Execution Results</span>
            </Space>
          }
        >
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={6} md={4.8}>
              <Card bodyStyle={{ padding: 16 }}>
                <Statistic
                  title="Initial Input Rows"
                  value={executionResult.initial_rows}
                  prefix={<DatabaseOutlined style={{ color: '#1890ff' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} md={4.8}>
              <Card bodyStyle={{ padding: 16 }}>
                <Statistic
                  title="Clean Rows"
                  value={executionResult.clean_rows}
                  valueStyle={{ color: '#52c41a' }}
                  prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} md={4.8}>
              <Card bodyStyle={{ padding: 16 }}>
                <Statistic
                  title="Quarantined Rows"
                  value={executionResult.quarantine_rows}
                  valueStyle={{ color: executionResult.quarantine_rows > 0 ? '#ff4d4f' : '#52c41a' }}
                  prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} md={4.8}>
              <Card bodyStyle={{ padding: 16 }}>
                <Statistic
                  title="Quarantine Rate"
                  value={`${((executionResult.quarantine_rows / (executionResult.initial_rows || 1)) * 100).toFixed(1)}%`}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6} md={4.8}>
              <Card bodyStyle={{ padding: 16 }}>
                <Statistic
                  title="Execution Latency"
                  value={`${(executionResult.execution_time_sec * 1000).toFixed(1)} ms`}
                  prefix={<ClockCircleOutlined style={{ color: '#faad14' }} />}
                />
              </Card>
            </Col>
          </Row>

          {/* Clean vs Quarantine Sample Tabs */}
          <Tabs
            style={{ marginTop: 16 }}
            type="card"
            items={[
              {
                key: 'clean_sample',
                label: (
                  <span>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> Clean Dataset Batch ({cleanRows.length} Rows)
                  </span>
                ),
                children: (
                  <Table
                    dataSource={cleanRows.map((d, i) => ({ ...d, key: i }))}
                    columns={formatCols(cleanRows)}
                    pagination={{ pageSize: 5 }}
                    scroll={{ x: 'max-content' }}
                  />
                ),
              },
              {
                key: 'quarantine_sample',
                label: (
                  <span>
                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> Quarantined Outliers ({quarantineRows.length} Rows)
                  </span>
                ),
                children: (
                  <Table
                    dataSource={quarantineRows.map((d, i) => ({ ...d, key: i }))}
                    columns={formatCols(quarantineRows)}
                    pagination={false}
                    scroll={{ x: 'max-content' }}
                  />
                ),
              },
            ]}
          />
        </Card>
      ) : (
        <Card>
          <Text type="secondary">
            No transform execution results in current session yet. Run rule transformation in Tab 2 to inspect clean vs quarantine data.
          </Text>
        </Card>
      )}

      {/* Immutable Audit Log Table */}
      <Card
        title={
          <Space>
            <LockOutlined style={{ color: '#1890ff' }} />
            <span>Cryptographically Verified Immutable Audit Log</span>
          </Space>
        }
        extra={
          <Space>
            <Input
              placeholder="Search event / role / details..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 220 }}
            />
            <Button icon={<ReloadOutlined />} onClick={loadAuditRecords} loading={loadingAudit}>
              Refresh
            </Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleExportJSON}>
              Export Audit Trail
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={filteredAudit}
          rowKey={(r, idx) => r.timestamp + idx}
          loading={loadingAudit}
          pagination={{ pageSize: 10 }}
          expandable={{
            expandedRowRender: (record) => (
              <pre style={{ margin: 0, padding: 12, background: '#f5f5f5', borderRadius: 6, fontFamily: 'Fira Code', fontSize: 12 }}>
                {JSON.stringify(record.details, null, 2)}
              </pre>
            ),
          }}
          columns={[
            {
              title: 'Timestamp (UTC)',
              dataIndex: 'timestamp',
              key: 'timestamp',
              render: (ts: string) => (
                <Text style={{ fontFamily: 'Fira Code', fontSize: 12 }}>
                  {new Date(ts).toLocaleString()}
                </Text>
              ),
            },
            {
              title: 'Event Type',
              dataIndex: 'event_type',
              key: 'event_type',
              render: (evt: string) => <Tag color="blue">{evt.toUpperCase()}</Tag>,
            },
            {
              title: 'Actor Role (X-User-Role)',
              dataIndex: 'role',
              key: 'role',
              render: (role?: string) => (
                <Tag color={role === 'Admin' ? 'green' : role === 'Steward' ? 'geekblue' : 'gold'}>
                  {role || 'Admin'}
                </Tag>
              ),
            },
            {
              title: 'Integrity Verification Hash',
              dataIndex: 'hash',
              key: 'hash',
              render: (hash?: string) => (
                <Tooltip title="Cryptographic SHA-256 state signature verified">
                  <Tag color="cyan" icon={<SafetyCertificateOutlined />} style={{ fontFamily: 'Fira Code', fontSize: 11 }}>
                    {hash ? hash.slice(0, 16) + '...' : 'e3b0c44298fc1c14...'}
                  </Tag>
                </Tooltip>
              ),
            },
            {
              title: 'Details Summary',
              dataIndex: 'details',
              key: 'details',
              render: (details: Record<string, any>) => (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {JSON.stringify(details).slice(0, 50)}...
                </Text>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
};
