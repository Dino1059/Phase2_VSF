import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Upload,
  Select,
  Tag,
  Badge,
  Space,
  Typography,
  Tabs,
  Form,
  Input,
  Switch,
  Modal,
  Popconfirm,
  Statistic,
  Tooltip,
  message,
} from 'antd';
import {
  UploadOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  TableOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  SettingOutlined,
  BarChartOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { apiService } from '../services/api';
import { ProfileReport, ColumnProfile, TargetSchemaField } from '../types';

const { Title, Text, Paragraph } = Typography;

// Preset sample datasets
const sampleDatasets: Record<string, { format: 'CSV' | 'Parquet' | 'JSON'; data: Record<string, any>[] }> = {
  'nyc_tlc_trip': {
    format: 'CSV',
    data: [
      { hvfhs_license_num: 'HV0003', dispatching_base_num: 'B02867', pickup_datetime: '2026-08-01 09:00:00', dropoff_datetime: '2026-08-01 09:18:22', driver_pay: 18.5, trip_miles: 3.4, passenger_count: 1 },
      { hvfhs_license_num: 'HV0003', dispatching_base_num: 'B02867', pickup_datetime: '2026-08-01 09:05:12', dropoff_datetime: '2026-08-01 09:32:10', driver_pay: -15.0, trip_miles: 5.8, passenger_count: 2 },
      { hvfhs_license_num: 'INVALID_VEND', dispatching_base_num: 'B02800', pickup_datetime: '2026-08-01 09:12:00', dropoff_datetime: '2026-08-01 09:25:00', driver_pay: 450.0, trip_miles: null, passenger_count: 1 },
      { hvfhs_license_num: 'HV0005', dispatching_base_num: 'B02867', pickup_datetime: '2026-08-01 09:15:30', dropoff_datetime: '2026-08-01 09:40:00', driver_pay: 24.2, trip_miles: 4.1, passenger_count: 1 },
      { hvfhs_license_num: 'HV0003', dispatching_base_num: 'B02867', pickup_datetime: '2026-08-01 09:20:00', dropoff_datetime: '2026-08-01 09:45:00', driver_pay: 0.0, trip_miles: 2.2, passenger_count: 3 },
    ],
  },
  'fintech_transactions': {
    format: 'Parquet',
    data: [
      { txn_id: 'TXN_1001', account_id: 'ACC_882', amount: 1500.0, txn_type: 'TRANSFER', timestamp: '2026-08-01T08:30:00Z', flag_fraud: 0 },
      { txn_id: 'TXN_1002', account_id: 'ACC_912', amount: -50.0, txn_type: 'WITHDRAWAL', timestamp: '2026-08-01T08:31:12Z', flag_fraud: 1 },
      { txn_id: 'TXN_1003', account_id: null, amount: 999999.0, txn_type: 'PAYMENT', timestamp: '2026-08-01T08:35:00Z', flag_fraud: 0 },
      { txn_id: 'TXN_1004', account_id: 'ACC_401', amount: 45.2, txn_type: 'DEPOSIT', timestamp: '2026-08-01T08:40:00Z', flag_fraud: 0 },
    ],
  },
  'customer_stream': {
    format: 'JSON',
    data: [
      { cust_id: 'C_501', email: 'john@example.com', country: 'US', signup_age: 29, tier: 'GOLD' },
      { cust_id: 'C_502', email: 'invalid_email_format', country: 'UK', signup_age: -5, tier: 'SILVER' },
      { cust_id: 'C_503', email: 'alice@domain.org', country: null, signup_age: 42, tier: 'PLATINUM' },
    ],
  },
};

const initialTargetSchema: TargetSchemaField[] = [
  { name: 'hvfhs_license_num', type: 'VARCHAR(16)', nullable: false, primaryKey: false, description: 'NYC TLC High-Volume License Identifier' },
  { name: 'dispatching_base_num', type: 'VARCHAR(16)', nullable: false, primaryKey: false, description: 'Base location dispatch code' },
  { name: 'pickup_datetime', type: 'TIMESTAMP', nullable: false, primaryKey: false, description: 'Trip commencement timestamp' },
  { name: 'dropoff_datetime', type: 'TIMESTAMP', nullable: false, primaryKey: false, description: 'Trip termination timestamp' },
  { name: 'driver_pay', type: 'DECIMAL(10,2)', nullable: false, primaryKey: false, description: 'Net driver compensation' },
  { name: 'trip_miles', type: 'FLOAT', nullable: false, primaryKey: false, description: 'Total trip distance' },
];

interface DatasetProfilerProps {
  onProfileComplete: (report: ProfileReport, rawData: Record<string, any>[]) => void;
}

export const DatasetProfiler: React.FC<DatasetProfilerProps> = ({ onProfileComplete }) => {
  const { canEditRules } = useRole();
  const [selectedDatasetKey, setSelectedDatasetKey] = useState<string>('nyc_tlc_trip');
  const [activeData, setActiveData] = useState<Record<string, any>[]>(sampleDatasets['nyc_tlc_trip'].data);
  const [fileFormat, setFileFormat] = useState<'CSV' | 'Parquet' | 'JSON'>('CSV');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ProfileReport | null>(null);
  const [targetSchema, setTargetSchema] = useState<TargetSchemaField[]>(initialTargetSchema);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const handleDatasetChange = (key: string) => {
    setSelectedDatasetKey(key);
    const ds = sampleDatasets[key];
    if (ds) {
      setActiveData(ds.data);
      setFileFormat(ds.format);
      setReport(null);
    }
  };

  const handleFileUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        if (file.name.endsWith('.json')) {
          const parsed = JSON.parse(text);
          const dataArr = Array.isArray(parsed) ? parsed : [parsed];
          setActiveData(dataArr);
          setFileFormat('JSON');
          message.success(`Loaded JSON file with ${dataArr.length} records`);
        } else if (file.name.endsWith('.csv')) {
          const lines = text.split('\n').filter((l) => l.trim().length > 0);
          const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
          const rows = lines.slice(1).map((line) => {
            const vals = line.split(',').map((v) => v.trim().replace(/^"|"$/g, ''));
            const obj: Record<string, any> = {};
            headers.forEach((h, idx) => {
              const val = vals[idx];
              const numVal = Number(val);
              obj[h] = !isNaN(numVal) && val !== '' ? numVal : val;
            });
            return obj;
          });
          setActiveData(rows);
          setFileFormat('CSV');
          message.success(`Parsed CSV with ${rows.length} rows`);
        } else {
          // Parquet or fallback simulation
          setFileFormat('Parquet');
          message.info(`Uploaded Parquet file (${file.name}). Extracting sample schema...`);
        }
        setReport(null);
      } catch (err) {
        message.error('Failed to parse uploaded file format.');
      }
    };
    reader.readAsText(file);
    return false; // Prevent default upload POST
  };

  const runProfiler = async () => {
    setLoading(true);
    try {
      const rep = await apiService.profileDataset(activeData);
      setReport(rep);
      onProfileComplete(rep, activeData);
      message.success(`Dataset profiled successfully! Snapshot ID: ${rep.snapshot_id}`);
    } catch (err) {
      message.error('Failed to profile dataset');
    } finally {
      setLoading(false);
    }
  };

  const handleAddField = (values: TargetSchemaField) => {
    setTargetSchema((prev) => [...prev, values]);
    setModalOpen(false);
    form.resetFields();
    message.success(`Added column "${values.name}" to Target Schema`);
  };

  const handleDeleteField = (name: string) => {
    setTargetSchema((prev) => prev.filter((f) => f.name !== name));
  };

  // Preview Columns
  const sampleColumns = activeData.length > 0
    ? Object.keys(activeData[0]).map((key) => ({
        title: key,
        dataIndex: key,
        key: key,
        render: (val: any) => (val === null || val === undefined ? <Text type="danger">&lt;NULL&gt;</Text> : String(val)),
      }))
    : [];

  // Schema Columns
  const schemaColumns = [
    {
      title: 'Column Name',
      dataIndex: 'column_name',
      key: 'column_name',
      render: (name: string) => <Text strong style={{ fontFamily: 'Fira Code' }}>{name}</Text>,
    },
    {
      title: 'Inferred Type',
      dataIndex: 'data_type',
      key: 'data_type',
      render: (type: string) => <Tag color="geekblue">{type}</Tag>,
    },
    {
      title: 'Null Count',
      dataIndex: 'null_count',
      key: 'null_count',
      render: (count: number) => (count > 0 ? <Text type="warning">{count}</Text> : <Text type="secondary">0</Text>),
    },
    {
      title: 'Null %',
      dataIndex: 'null_percentage',
      key: 'null_percentage',
      render: (pct: number) => (
        <Badge
          status={pct > 0 ? 'warning' : 'success'}
          text={`${pct.toFixed(1)}%`}
        />
      ),
    },
    {
      title: 'Distinct Values',
      dataIndex: 'distinct_count',
      key: 'distinct_count',
    },
    {
      title: 'Sample Data / Range',
      key: 'sample',
      render: (_: any, r: ColumnProfile) => (
        <Text style={{ fontSize: 12, color: '#666', fontFamily: 'Fira Code' }}>
          [{r.sample_values ? r.sample_values.join(', ') : 'N/A'}]
        </Text>
      ),
    },
    {
      title: 'Health Status',
      dataIndex: 'health_status',
      key: 'health_status',
      render: (status: string) => {
        if (status === 'Warning' || status === 'Drifting') {
          return <Tag color="orange" icon={<ExclamationCircleOutlined />}>{status}</Tag>;
        }
        return <Tag color="green" icon={<CheckCircleOutlined />}>Good</Tag>;
      },
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* Top Banner: Dataset Selector & Trigger */}
      <Card
        style={{ borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}
        title={
          <Space>
            <TableOutlined style={{ color: '#1890ff' }} />
            <span>Dataset Ingestion & Invariant Profiler</span>
          </Space>
        }
        extra={
          <Space>
            <Tag color={fileFormat === 'CSV' ? 'green' : fileFormat === 'Parquet' ? 'purple' : 'cyan'}>
              Format: {fileFormat}
            </Tag>
            <Button
              type="primary"
              icon={<ThunderboltOutlined spin={loading} />}
              loading={loading}
              onClick={runProfiler}
              style={{ background: 'linear-gradient(135deg, #1890ff 0%, #096dd9 100%)', border: 'none' }}
            >
              Run AI Profiler & Rule Discovery
            </Button>
          </Space>
        }
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} md={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">Select Ingestion Dataset Stream:</Text>
              <Select
                value={selectedDatasetKey}
                onChange={handleDatasetChange}
                style={{ width: '100%' }}
                options={[
                  { value: 'nyc_tlc_trip', label: '🚕 NYC TLC Trip Records Sample (CSV)' },
                  { value: 'fintech_transactions', label: '💳 FinTech High-Frequency Payments (Parquet)' },
                  { value: 'customer_stream', label: '👤 E-Commerce Customer Profile Stream (JSON)' },
                ]}
              />
            </Space>
          </Col>
          <Col xs={24} md={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">Or Upload Custom File (.csv, .parquet, .json):</Text>
              <Upload beforeUpload={handleFileUpload} showUploadList={false} accept=".csv,.json,.parquet">
                <Button icon={<UploadOutlined />}>Choose Data File</Button>
              </Upload>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Profiling Statistics Summary */}
      {report && (
        <Row gutter={[16, 16]}>
          <Col xs={12} sm={6} md={4.8}>
            <Card bodyStyle={{ padding: 16 }}>
              <Statistic
                title="Total Rows"
                value={report.row_count}
                prefix={<FileTextOutlined style={{ color: '#1890ff' }} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6} md={4.8}>
            <Card bodyStyle={{ padding: 16 }}>
              <Statistic
                title="Columns"
                value={report.column_count}
                prefix={<TableOutlined style={{ color: '#722ed1' }} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6} md={4.8}>
            <Card bodyStyle={{ padding: 16 }}>
              <Statistic
                title="Duplicate Rows"
                value={report.duplicate_count}
                valueStyle={{ color: report.duplicate_count > 0 ? '#faad14' : '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6} md={4.8}>
            <Card bodyStyle={{ padding: 16 }}>
              <Statistic
                title="Null Fields"
                value={report.columns.reduce((acc, c) => acc + c.null_count, 0)}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6} md={4.8}>
            <Card bodyStyle={{ padding: 16 }}>
              <Statistic
                title="Snapshot Hash"
                value={report.snapshot_id}
                valueStyle={{ fontSize: 14, fontFamily: 'Fira Code' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Detail Tabs: Raw Preview, Inferred Column Schema, Target Schema Specification */}
      <Tabs
        type="card"
        items={[
          {
            key: 'schema',
            label: (
              <span>
                <BarChartOutlined /> Inferred Schema & Health Analysis
              </span>
            ),
            children: (
              <Card>
                <Table
                  dataSource={report ? report.columns : []}
                  columns={schemaColumns}
                  rowKey="column_name"
                  pagination={false}
                  locale={{ emptyText: 'Click "Run AI Profiler & Rule Discovery" to generate schema analysis.' }}
                />
              </Card>
            ),
          },
          {
            key: 'preview',
            label: (
              <span>
                <TableOutlined /> Raw Data Sample ({activeData.length} Rows)
              </span>
            ),
            children: (
              <Card>
                <Table
                  dataSource={activeData.map((d, i) => ({ ...d, key: i }))}
                  columns={sampleColumns}
                  pagination={{ pageSize: 5 }}
                  scroll={{ x: 'max-content' }}
                />
              </Card>
            ),
          },
          {
            key: 'target_schema',
            label: (
              <span>
                <SettingOutlined /> Target Schema Governance Specs
              </span>
            ),
            children: (
              <Card
                extra={
                  canEditRules && (
                    <Button
                      type="dashed"
                      icon={<PlusOutlined />}
                      onClick={() => setModalOpen(true)}
                    >
                      Add Target Field
                    </Button>
                  )
                }
              >
                <Table
                  dataSource={targetSchema}
                  rowKey="name"
                  pagination={false}
                  columns={[
                    {
                      title: 'Field Name',
                      dataIndex: 'name',
                      key: 'name',
                      render: (n: string) => <Text strong style={{ fontFamily: 'Fira Code' }}>{n}</Text>,
                    },
                    {
                      title: 'Data Type',
                      dataIndex: 'type',
                      key: 'type',
                      render: (t: string) => <Tag color="blue">{t}</Tag>,
                    },
                    {
                      title: 'Nullable',
                      dataIndex: 'nullable',
                      key: 'nullable',
                      render: (nulla: boolean) => (
                        <Tag color={nulla ? 'default' : 'red'}>{nulla ? 'Nullable' : 'NOT NULL'}</Tag>
                      ),
                    },
                    {
                      title: 'Primary Key',
                      dataIndex: 'primaryKey',
                      key: 'primaryKey',
                      render: (pk: boolean) => pk && <Tag color="gold">PK</Tag>,
                    },
                    {
                      title: 'Description',
                      dataIndex: 'description',
                      key: 'description',
                    },
                    {
                      title: 'Actions',
                      key: 'action',
                      render: (_: any, r: TargetSchemaField) =>
                        canEditRules && (
                          <Popconfirm title="Remove field spec?" onConfirm={() => handleDeleteField(r.name)}>
                            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                          </Popconfirm>
                        ),
                    },
                  ]}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* Modal for Adding Target Field */}
      <Modal
        title="Define Target Schema Field"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleAddField}>
          <Form.Item name="name" label="Column Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. driver_pay" />
          </Form.Item>
          <Form.Item name="type" label="Data Type" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'VARCHAR(64)', label: 'VARCHAR(64)' },
                { value: 'DECIMAL(10,2)', label: 'DECIMAL(10,2)' },
                { value: 'INTEGER', label: 'INTEGER' },
                { value: 'FLOAT', label: 'FLOAT' },
                { value: 'TIMESTAMP', label: 'TIMESTAMP' },
                { value: 'BOOLEAN', label: 'BOOLEAN' },
              ]}
            />
          </Form.Item>
          <Form.Item name="nullable" label="Nullable" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
          <Form.Item name="primaryKey" label="Primary Key" valuePropName="checked" initialValue={false}>
            <Switch />
          </Form.Item>
          <Form.Item name="description" label="Field Description">
            <Input.TextArea placeholder="Specification notes..." />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};
