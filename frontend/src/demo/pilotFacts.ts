/** Measured from data_new on 2026-08-20. Not industry/eval theater. */
export const PILOT_BATCH = {
  windowStart: '2026-01-01',
  windowEnd: '2026-01-15',
  ingress: 'batch window' as const,
  vins: 60,
  days: 15,
};

export const PILOT_CLEAN = {
  source: 'data_new/vingroup_pilot_dataset',
  faultInjected: false,
  telemetry: 86400,
  chargingSessions: 1331,
  trips: 10382,
  socBelowZero: 0,
  voltageOver1000: 0,
  gpsOutsideHanoi: 0,
  openIncidents: 0,
};

export const PILOT_FAULTY = {
  source: 'data_new/db/vingroup_pilot.db',
  faultInjected: true,
  telemetry: 86400,
  chargingRows: 1513,
  chargingSessions: 1331,
  duplicateSessions: 182,
  trips: 10382,
  socBelowZero: 172,
  socMin: -15,
  voltageOver1000: 131,
  voltageMax: 5000,
  gpsOutsideHanoi: 103,
  openIncidents: 8,
  criticalOpen: 6,
  highOpen: 2,
  focusIncident: 'inc-5c6fd288',
  quarantine: 0,
  auditLog: 0,
  authorizations: 0,
  proposedRules: 3,
  hollowBmsCols: ['charging_rate_kw', 'fault_code'] as const,
};
