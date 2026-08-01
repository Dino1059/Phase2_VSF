import React, { useState } from 'react';
import { ConfigProvider, Layout, Tabs, theme, Space, Typography, Card } from 'antd';
import {
  TableOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { RoleProvider } from './context/RoleContext';
import { Header } from './components/Header';
import { DatasetProfiler } from './components/DatasetProfiler';
import { RuleGovernance } from './components/RuleGovernance';
import { ScheduleManager } from './components/ScheduleManager';
import { AnomalyDiagnosis } from './components/AnomalyDiagnosis';
import { AuditTrace } from './components/AuditTrace';
import { ProfileReport, ExecuteTransformResponse } from './types';

const { Content, Footer } = Layout;

export const AppContent: React.FC = () => {
  const [activeTabKey, setActiveTabKey] = useState<string>('tab1');
  const [profileReport, setProfileReport] = useState<ProfileReport | null>(null);
  const [rawData, setRawData] = useState<Record<string, any>[]>([]);
  const [executionResult, setExecutionResult] = useState<ExecuteTransformResponse | null>(null);

  const handleProfileComplete = (report: ProfileReport, data: Record<string, any>[]) => {
    setProfileReport(report);
    setRawData(data);
  };

  const handleExecutionComplete = (result: ExecuteTransformResponse) => {
    setExecutionResult(result);
    // Auto navigate to Tab 5 to view execution results
    setActiveTabKey('tab5');
  };

  const items = [
    {
      key: 'tab1',
      label: (
        <span>
          <TableOutlined /> Tab 1: Dataset Profiler & Schema
        </span>
      ),
      children: <DatasetProfiler onProfileComplete={handleProfileComplete} />,
    },
    {
      key: 'tab2',
      label: (
        <span>
          <SafetyCertificateOutlined /> Tab 2: Rule Governance Review
        </span>
      ),
      children: (
        <RuleGovernance rawData={rawData} onExecutionComplete={handleExecutionComplete} />
      ),
    },
    {
      key: 'tab3',
      label: (
        <span>
          <ClockCircleOutlined /> Tab 3: Schedule Manager
        </span>
      ),
      children: <ScheduleManager />,
    },
    {
      key: 'tab4',
      label: (
        <span>
          <WarningOutlined /> Tab 4: Anomaly Timeline & RCA
        </span>
      ),
      children: <AnomalyDiagnosis />,
    },
    {
      key: 'tab5',
      label: (
        <span>
          <LockOutlined /> Tab 5: Execution Results & Audit Trace
        </span>
      ),
      children: <AuditTrace executionResult={executionResult} rawData={rawData} />,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <Header />
      <Content style={{ padding: '24px 32px', maxWidth: 1600, margin: '0 auto', width: '100%' }}>
        <Tabs
          activeKey={activeTabKey}
          onChange={setActiveTabKey}
          type="line"
          size="large"
          style={{ marginBottom: 24 }}
          items={items}
        />
      </Content>
      <Footer style={{ textAlign: 'center', background: '#001529', color: '#8c8c8c', fontSize: 12 }}>
        DataTrust OS v2.0 © 2026 — Autonomous AI-Augmented Data Quality & Governance Operating System
      </Footer>
    </Layout>
  );
};

export const App: React.FC = () => {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1890ff',
          borderRadius: 6,
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
      }}
    >
      <RoleProvider>
        <AppContent />
      </RoleProvider>
    </ConfigProvider>
  );
};

export default App;
