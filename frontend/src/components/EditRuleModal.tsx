import React, { useEffect } from 'react';
import { Modal, Form, Input, Select, InputNumber, Space, Typography } from 'antd';
import { RuleSchema } from '../types';

const { Text } = Typography;

interface EditRuleModalProps {
  open: boolean;
  rule: RuleSchema | null;
  onCancel: () => void;
  onSave: (updatedRule: RuleSchema) => void;
}

export const EditRuleModal: React.FC<EditRuleModalProps> = ({ open, rule, onCancel, onSave }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (rule) {
      form.setFieldsValue({
        rule_id: rule.rule_id,
        rule_type: rule.rule_type,
        target_column: rule.target_column,
        action: rule.action,
        severity: rule.severity,
        description: rule.description,
        param_min: rule.parameters?.min ?? 0,
        param_max: rule.parameters?.max ?? 100,
        param_pattern: rule.parameters?.pattern ?? '',
      });
    }
  }, [rule, form]);

  const handleFinish = (values: any) => {
    if (!rule) return;
    const parameters: Record<string, any> = { ...rule.parameters };

    if (values.rule_type === 'RANGE_CHECK') {
      parameters.min = values.param_min;
      parameters.max = values.param_max;
    } else if (values.rule_type === 'REGEX_MATCH') {
      parameters.pattern = values.param_pattern;
    }

    const updatedRule: RuleSchema = {
      ...rule,
      rule_type: values.rule_type,
      target_column: values.target_column,
      action: values.action,
      severity: values.severity,
      description: values.description,
      parameters,
    };
    onSave(updatedRule);
  };

  return (
    <Modal
      title={`Edit Governance Rule: ${rule?.rule_id ?? ''}`}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleFinish}>
        <Form.Item name="target_column" label="Target Column" rules={[{ required: true }]}>
          <Input />
        </Form.Item>

        <Form.Item name="rule_type" label="Rule Type" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'RANGE_CHECK', label: 'RANGE_CHECK (Min / Max Bound)' },
              { value: 'REGEX_MATCH', label: 'REGEX_MATCH (Pattern Validator)' },
              { value: 'IMPUTE_NULL', label: 'IMPUTE_NULL (Strategy Imputation)' },
              { value: 'DATETIME_FORMAT', label: 'DATETIME_FORMAT (ISO Standard)' },
            ]}
          />
        </Form.Item>

        <Form.Item name="action" label="Rule Action" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'QUARANTINE', label: 'QUARANTINE (Move to quarantine table)' },
              { value: 'REJECT', label: 'REJECT (Drop invalid row)' },
              { value: 'IMPUTE_MEDIAN', label: 'IMPUTE_MEDIAN (Replace null with median)' },
              { value: 'FLAG', label: 'FLAG (Mark row for review)' },
            ]}
          />
        </Form.Item>

        <Form.Item name="severity" label="Severity Level" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'High', label: 'High (Blocks Pipeline)' },
              { value: 'Medium', label: 'Medium (Alert & Quarantine)' },
              { value: 'Low', label: 'Low (Audit Log Only)' },
            ]}
          />
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prevValues, currentValues) => prevValues.rule_type !== currentValues.rule_type}
        >
          {({ getFieldValue }) =>
            getFieldValue('rule_type') === 'RANGE_CHECK' ? (
              <Space style={{ display: 'flex', marginBottom: 16 }}>
                <Form.Item name="param_min" label="Min Bound" style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item name="param_max" label="Max Bound" style={{ flex: 1 }}>
                  <InputNumber style={{ width: '100%' }} />
                </Form.Item>
              </Space>
            ) : getFieldValue('rule_type') === 'REGEX_MATCH' ? (
              <Form.Item name="param_pattern" label="Regex Pattern">
                <Input placeholder="e.g. ^HV[0-9]{4}$" />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <Form.Item name="description" label="Rule Specification & Rationale">
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
};
