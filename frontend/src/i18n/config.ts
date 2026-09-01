import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import commonEn from './locales/en/common.json';
import chatEn from './locales/en/chat.json';
import agentsEn from './locales/en/agents.json';
import rulesEn from './locales/en/rules.json';
import profilerEn from './locales/en/profiler.json';
import auditEn from './locales/en/audit.json';
import pipelineEn from './locales/en/pipeline.json';

import commonVi from './locales/vi/common.json';
import chatVi from './locales/vi/chat.json';
import agentsVi from './locales/vi/agents.json';
import rulesVi from './locales/vi/rules.json';
import profilerVi from './locales/vi/profiler.json';
import auditVi from './locales/vi/audit.json';
import pipelineVi from './locales/vi/pipeline.json';

const resources = {
  en: {
    common: commonEn,
    chat: chatEn,
    agents: agentsEn,
    rules: rulesEn,
    profiler: profilerEn,
    audit: auditEn,
    pipeline: pipelineEn,
  },
  vi: {
    common: commonVi,
    chat: chatVi,
    agents: agentsVi,
    rules: rulesVi,
    profiler: profilerVi,
    audit: auditVi,
    pipeline: pipelineVi,
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: localStorage.getItem('datatrust-lang') || 'vi',
  fallbackLng: 'vi',
  defaultNS: 'common',
  ns: ['common', 'chat', 'agents', 'rules', 'profiler', 'audit', 'pipeline'],
  interpolation: { escapeValue: false },
});

export default i18n;
