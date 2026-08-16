import i18n from './config';

export interface LayerTokenMeta {
  id: 'L1' | 'L2' | 'L3' | 'L4';
  nameKey: string;
  colorClass: string;
  hexColor: string;
  iconName: string;
  defaultLabel: {
    vi: string;
    en: string;
  };
}

export const DEFAULT_VI_STRINGS = {
  reliabilityOverview: 'Tổng quan độ tin cậy',
  incident: 'Sự cố',
  evidence: 'Bằng chứng',
  hypothesis: 'Giả thuyết',
  preventiveControl: 'Kiểm soát phòng ngừa',
  operationalRecommendation: 'Khuyến nghị vận hành',
} as const;

export const DEFAULT_EN_STRINGS = {
  reliabilityOverview: 'Reliability Overview',
  incident: 'Incident',
  evidence: 'Evidence',
  hypothesis: 'Hypothesis',
  preventiveControl: 'Preventive Control',
  operationalRecommendation: 'Operational Recommendation',
} as const;

export type CentralizedLocaleKey = keyof typeof DEFAULT_VI_STRINGS;

/**
 * 4 Stable Categorical L1-L4 Reliability Layer Tokens + Metadata Map
 */
export const LAYER_TOKENS: Record<'L1' | 'L2' | 'L3' | 'L4', LayerTokenMeta> = {
  L1: {
    id: 'L1',
    nameKey: 'layerL1Label',
    colorClass: 'layer-l1',
    hexColor: '#ef4444',
    iconName: 'ShieldAlert',
    defaultLabel: {
      vi: 'L1 - Ràng buộc cứng & Schema',
      en: 'L1 - Hard Constraints & Schema',
    },
  },
  L2: {
    id: 'L2',
    nameKey: 'layerL2Label',
    colorClass: 'layer-l2',
    hexColor: '#f59e0b',
    iconName: 'Activity',
    defaultLabel: {
      vi: 'L2 - Trôi ngắt ngữ cảnh & Thống kê',
      en: 'L2 - Statistical & Contextual Drift',
    },
  },
  L3: {
    id: 'L3',
    nameKey: 'layerL3Label',
    colorClass: 'layer-l3',
    hexColor: '#3b82f6',
    iconName: 'Network',
    defaultLabel: {
      vi: 'L3 - Toàn vẹn quan hệ liên thực thể',
      en: 'L3 - Cross-Entity Relational Integrity',
    },
  },
  L4: {
    id: 'L4',
    nameKey: 'layerL4Label',
    colorClass: 'layer-l4',
    hexColor: '#a855f7',
    iconName: 'Brain',
    defaultLabel: {
      vi: 'L4 - Độ tin cậy hệ thống & Thời gian',
      en: 'L4 - Systemic Reliability & Temporal',
    },
  },
};

/**
 * Helper to retrieve centralized locale strings with Vietnamese defaults
 */
export const getLocaleString = (
  key: CentralizedLocaleKey,
  lang: 'vi' | 'en' = (i18n.language as 'vi' | 'en') || 'vi'
): string => {
  const currentLang = lang === 'en' ? 'en' : 'vi';
  if (currentLang === 'vi') {
    return DEFAULT_VI_STRINGS[key] || DEFAULT_EN_STRINGS[key];
  }
  return DEFAULT_EN_STRINGS[key] || DEFAULT_VI_STRINGS[key];
};

export const changeLanguage = (lang: 'vi' | 'en'): Promise<unknown> => {
  localStorage.setItem('datatrust-lang', lang);
  return i18n.changeLanguage(lang);
};

export { i18n };
export default i18n;
