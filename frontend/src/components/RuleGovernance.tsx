import React, { useState } from 'react';
import {
  Card,
  Table,
  Button,
  Tag,
  Space,
  Typography,
  Badge,
  Steps,
  Select,
  Tooltip,
  Popconfirm,
  Row,
  Col,
  Statistic,
  Drawer,
  message,
  Alert,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  SafetyCertificateOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  BulbOutlined,
} from '@ant-design/icons';
import { useRole } from '../context/RoleContext';
import { apiService } from '../services/api';
import { RuleSchema, ProposeRulesResponse } from '../types';
import { EditRuleModal } from './EditRuleModal';

const { Title, Text, Paragraph } = Typography;

const defaultRules: RuleSchema[] = [
  {
    rule_id: 'RULE_PAY_BOUNDS_001',
    rule_type: 'RANGE_CHECK',
    target_column: 'driver_pay',
    action: 'QUARANTINE',
    parameters: { min: 0.0, max: 250.0 },
    severity: 'High',
    description: 'Driver pay must be non-negative and capped at $250.00 per trip.',
    status: 'Proposed',
    confidence_score: 97.4,
    evidence: 'Discovered 2 outlier records with driver_pay < $0.0 (-$15.00) and $450.00 in initial profiling batch.',
  },
  {
    rule_id: 'RULE_LICENSE_REGEX_002',
    rule_type: 'REGEX_MATCH',
    target_column: 'hvfhs_license_num',
    action: 'QUARANTINE',
    parameters: { pattern: '^HV[0-9]{4}$' },
    severity: 'High',
    description: 'License number must match NYC TLC format: HV followed by 4 digits.',
    status: 'Proposed',
    confidence_score: 99.1,
    evidence: 'Record index 2 contained vendor string "INVALID_VEND" failing regex validation.',
  },
  {
    rule_id: 'RULE_MILES_IMPUTE_003',
    rule_type: 'IMPUTE_NULL',
    target_column: 'trip_miles',
    action: 'IMPUTE_MEDIAN',
    parameters: { strategy: 'median', default_value: 2.5 },
    severity: 'Medium',
    description: 'Impute missing trip miles with median trip distance (2.5 miles).',
    status: 'Proposed',
    confidence_score: 91.8,
    evidence: 'Missing value rate of 4.2% detected. Median distance imputation recommended.',
  },
  {
    rule_id: 'RULE_DATETIME_VALIDATE_004',
    rule_type: 'DATETIME_FORMAT',
    target_column: 'pickup_datetime',
    action: 'REJECT',
    parameters: { format: 'YYYY-MM-DD HH:mm:ss' },
    severity: 'Low',
    description: 'Pickup timestamp must conform to ISO-8601 standard format.',
    status: 'Proposed',
    confidence_score: 85.0,
    evidence: 'Inconsistent timestamp string formats detected across microservices.',
  },
];

interface RuleGovernanceProps {
  rawData: Record<string, any>[];
  onExecutionComplete: (result: any) => void;
}

export const RuleGovernance: React.FC<RuleGovernanceProps> = ({ rawData, onExecutionComplete }) => {
  const { canEditRules, canExecuteTransforms } = useRole();
  const [rules, setRules] = useState<RuleSchema[]>(defaultRules);
  const [variant, setVariant] = useState<string>('A1');
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [workflowStep, setWorkflowStep] = useState<number>(2); // RULES_PROPOSED = step 2
  const [selectedRuleForEvidence, setSelectedRuleForEvidence] = useState<RuleSchema | null>(null);
  const [editingRule, setEditingRule] = useState<RuleSchema | null>(null);
  const [reasoningText, setReasoningText] = useState<string>(
    'AI Agent autonomously synthesized invariant rules based on distribution bounds, column nullability, and TLC schema constraints.'
  );

  const handleProposeRules = async () => {
    setLoading(true);
    try {
      const res: ProposeRulesResponse = await apiService.proposeRules(rawData, variant);
      setRules(res.rules);
      setReasoningText(res.reasoning);
      setWorkflowStep(2);
      message.success(`Generated ${res.rules.length} proposed rules using variant ${res.variant}`);
    } catch (err) {
      message.error('Failed to propose rules');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (ruleId: string, newStatus: 'Approved' | 'Rejected') => {
    setRules((prev) =>
      prev.map((r) => (r.rule_id === ruleId ? { ...r, status: newStatus } : r))
    );
    setWorkflowStep(3); // HITL_REVIEWED
    message.info(`Rule ${ruleId} marked as ${newStatus}`);
  };

  const handleBatchApproveHighConfidence = () => {
    setRules((prev) =>
      prev.map((r) =>
        (r.confidence_score ?? 0) >= 95 ? { ...r, status: 'Approved' } : r
      )
    );
    setWorkflowStep(3);
    message.success('Auto-approved all rules with confidence ≥ 95%');
  };

  const handleBatchApproveAll = () => {
    setRules((prev) => prev.map((r) => ({ ...r, status: 'Approved' })));
    setWorkflowStep(3);
    message.success('All rules approved!');
  };

  const handleSaveEditedRule = (updated: RuleSchema) => {
    setRules((prev) => prev.map((r) => (r.rule_id === updated.rule_id ? updated : r)));
    setEditingRule(null);
    setWorkflowStep(3);
    message.success(`Updated rule ${updated.rule_id}`);
  };

  const handleExecuteTransform = async () => {
    const approvedRules = rules.filter((r) => r.status === 'Approved' || r.status === 'Proposed');
    if (approvedRules.length === 0) {
      message.warning('No active or approved rules to execute!');
      return;
    }

    setExecuting(true);
    try {
      const res = await apiService.executeTransform(rawData, approvedRules);
      setWorkflowStep(4); // EXECUTED / COMPLETED
      onExecutionComplete(res);
      message.success(`Execution complete! ${res.clean_rows} clean rows, ${res.quarantine_rows} quarantined.`);
    } catch (err) {
      message.error('Failed to execute transform');
    } finally {
      setExecuting(false);
    }
  };

  const approvedCount = rules.filter((r) => r.status === 'Approved').length;
  const rejectedCount = rules.filter((r) => r.status === 'Rejected').length;
  const proposedCount = rules.filter((r) => r.status === 'Proposed').length;

  const getConfidenceBadge = (score?: number) => {
    const val = score ?? 90;
    if (val >= 95) return <Tag color="success" icon={<CheckCircleOutlined />}>{val}% High Confidence</Tag>;
    if (val >= 85) return <Tag color="warning" icon={<BulbOutlined />}>{val}% Moderate</Tag>;
    return <Tag color="error">{val}% Low Confidence</Tag>;
  };

  const getSeverityTag = (sev: RuleSchema['severity']) => {
    switch (sev) {
      case 'High':
        return <Tag color="red">High Severity</Tag>;
      case 'Medium':
        return <Tag color="orange">Medium Severity</Tag>;
      case 'Low':
        return <Tag color="blue">Low Severity</Tag>;
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* Workflow Progress Steps */}
      <Card bodyStyle={{ padding: '16px 24px' }}>
        <Steps
          current={workflowStep}
          items={[
            { title: 'INIT', description: 'Raw Data Loaded' },
            { title: 'PROFILED', description: 'Invariants Detected' },
            { title: 'RULES PROPOSED', description: 'AI Agent Generated Rules' },
            { title: 'HITL REVIEWED', description: 'Steward Review & Action' },
            { title: 'EXECUTED & COMPLETED', description: 'Quarantine & Audit' },
          ]}
        />
      </Card>

      {/* Control Banner: Variant Picker, Generation Trigger, Batch Actions */}
      <Card
        title={
          <Space>
            <RobotOutlined style={{ color: '#1890ff', fontSize: 20 }} />
            <span>AI Rule Synthesis & Governance Review</span>
          </Space>
        }
        extra={
          <Space>
            <Text type="secondary">Agent Variant:</Text>
            <Select
              value={variant}
              onChange={setVariant}
              style={{ width: 140 }}
              options={[
                { value: 'A1', label: '🤖 A1 Agent (LLM + Dynamic Tools)' },
                { value: 'C0', label: '⚡ C0 Baseline (Deterministic)' },
                { value: 'C1', label: '🧠 C1 Baseline (Heuristic LLM)' },
              ]}
            />
            <Button
              type="primary"
              icon={<ThunderboltOutlined spin={loading} />}
              loading={loading}
              onClick={handleProposeRules}
            >
              Re-Synthesize Rules
            </Button>
          </Space>
        }
      >
        <Alert
          message="AI Agent Reasoning Summary"
          description={reasoningText}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        {/* Governance Metrics & Batch Actions */}
        <Row gutter={[16, 16]} align="middle" style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card bodyStyle={{ padding: 12 }}>
              <Statistic title="Total Proposed" value={rules.length} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bodyStyle={{ padding: 12 }}>
              <Statistic title="Approved Rules" value={approvedCount} valueStyle={{ color: '#52c41a' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bodyStyle={{ padding: 12 }}>
              <Statistic title="Rejected Rules" value={rejectedCount} valueStyle={{ color: '#ff4d4f' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bodyStyle={{ padding: 12 }}>
              <Statistic title="Pending Review" value={proposedCount} valueStyle={{ color: '#faad14' }} />
            </Card>
          </Col>
        </Row>

        <Space style={{ marginBottom: 16 }}>
          {canEditRules && (
            <>
              <Button type="dashed" icon={<CheckOutlined />} onClick={handleBatchApproveHighConfidence}>
                Approve High Confidence (&ge;95%)
              </Button>
              <Button type="default" icon={<SafetyCertificateOutlined />} onClick={handleBatchApproveAll}>
                Approve All Rules
              </Button>
            </>
          )}

          {canExecuteTransforms && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined spin={executing} />}
              loading={executing}
              onClick={handleExecuteTransform}
              style={{ background: 'linear-gradient(135deg, #52c41a 0%, #389e0d 100%)', border: 'none' }}
            >
              Execute Data Transformation & Quarantine
            </Button>
          )}
        </Space>

        {/* Rule Governance Table */}
        <Table
          dataSource={rules}
          rowKey="rule_id"
          pagination={false}
          columns={[
            {
              title: 'Rule ID',
              dataIndex: 'rule_id',
              key: 'rule_id',
              render: (id: string) => <Text strong style={{ fontFamily: 'Fira Code' }}>{id}</Text>,
            },
            {
              title: 'Target Column',
              dataIndex: 'target_column',
              key: 'target_column',
              render: (col: string) => <Tag color="geekblue">{col}</Tag>,
            },
            {
              title: 'Rule Type / Action',
              key: 'type_action',
              render: (_: any, r: RuleSchema) => (
                <Space direction="vertical" size={2}>
                  <Text strong style={{ fontSize: 13 }}>{r.rule_type}</Text>
                  <Tag color="purple">{r.action}</Tag>
                </Space>
              ),
            },
            {
              title: 'Parameters',
              dataIndex: 'parameters',
              key: 'parameters',
              render: (params: Record<string, any>) => (
                <Text style={{ fontFamily: 'Fira Code', fontSize: 11, color: '#555' }}>
                  {JSON.stringify(params)}
                </Text>
              ),
            },
            {
              title: 'Severity & AI Confidence',
              key: 'confidence',
              render: (_: any, r: RuleSchema) => (
                <Space direction="vertical" size={4}>
                  {getSeverityTag(r.severity)}
                  {getConfidenceBadge(r.confidence_score)}
                </Space>
              ),
            },
            {
              title: 'Status',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => {
                if (status === 'Approved') return <Tag color="green">Approved</Tag>;
                if (status === 'Rejected') return <Tag color="red">Rejected</Tag>;
                return <Tag color="blue">Proposed</Tag>;
              },
            },
            {
              title: 'Evidence',
              key: 'evidence',
              render: (_: any, r: RuleSchema) => (
                <Button
                  type="text"
                  icon={<EyeOutlined />}
                  onClick={() => setSelectedRuleForEvidence(r)}
                >
                  View Rationale
                </Button>
              ),
            },
            {
              title: 'Actions',
              key: 'actions',
              render: (_: any, r: RuleSchema) =>
                canEditRules ? (
                  <Space size="small">
                    <Tooltip title="Approve Rule">
                      <Button
                        type="primary"
                        ghost
                        icon={<CheckOutlined />}
                        size="small"
                        disabled={r.status === 'Approved'}
                        onClick={() => handleStatusChange(r.rule_id, 'Approved')}
                      />
                    </Tooltip>
                    <Tooltip title="Edit Rule Parameters">
                      <Button
                        type="default"
                        icon={<EditOutlined />}
                        size="small"
                        onClick={() => setEditingRule(r)}
                      />
                    </Tooltip>
                    <Tooltip title="Reject Rule">
                      <Button
                        danger
                        ghost
                        icon={<CloseOutlined />}
                        size="small"
                        disabled={r.status === 'Rejected'}
                        onClick={() => handleStatusChange(r.rule_id, 'Rejected')}
                      />
                    </Tooltip>
                  </Space>
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>Read Only</Text>
                ),
            },
          ]}
        />
      </Card>

      {/* Evidence & Rationale Drawer */}
      <Drawer
        title={`AI Evidence & Statistical Rationale: ${selectedRuleForEvidence?.rule_id ?? ''}`}
        placement="right"
        width={450}
        onClose={() => setSelectedRuleForEvidence(null)}
        open={!!selectedRuleForEvidence}
      >
        {selectedRuleForEvidence && (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <Text type="secondary">Rule Description:</Text>
              <Paragraph strong>{selectedRuleForEvidence.description}</Paragraph>
            </div>

            <div>
              <Text type="secondary">Confidence Level:</Text>
              <div style={{ marginTop: 8 }}>
                {getConfidenceBadge(selectedRuleForEvidence.confidence_score)}
              </div>
            </div>

            <div>
              <Text type="secondary">Discovered Anomalies / Violating Invariants:</Text>
              <Alert
                message="Outlier Evidence Analysis"
                description={selectedRuleForEvidence.evidence || 'No empirical violations detected in sample.'}
                type="warning"
                showIcon
                style={{ marginTop: 8 }}
              />
            </div>

            <div>
              <Text type="secondary">Execution Impact:</Text>
              <Paragraph style={{ fontSize: 13, background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                Enforcing this rule will automatically route non-conforming records to the isolated quarantine environment for compliance verification.
              </Paragraph>
            </div>
          </Space>
        )}
      </Drawer>

      {/* Edit Rule Modal */}
      <EditRuleModal
        open={!!editingRule}
        rule={editingRule}
        onCancel={() => setEditingRule(null)}
        onSave={handleSaveEditedRule}
      />
    </Space>
  );
};
