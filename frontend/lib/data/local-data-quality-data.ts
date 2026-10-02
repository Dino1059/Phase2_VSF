import type { ColumnProfile, DataQualityDataSource, DatasetProfile } from './data-quality-types';
import { apiBridge } from '../api-bridge';

export class LocalCsvDataQualityDataSource implements DataQualityDataSource {
  async getDatasetProfile(datasetKey: string = 'ride_hailing_xanh_sm_trips'): Promise<DatasetProfile> {
    try {
      const data = await apiBridge.fetchDatasetProfile(datasetKey);
      const cols: ColumnProfile[] = (data.columns || []).map((c: any) => ({
        name: c.name || c.column_name,
        datatype: c.datatype || c.data_type || 'string',
        distinctCount: c.unique_count || 10,
        nullRate: c.null_pct || 0,
        summary: `Min: ${c.min_val ?? 'N/A'} · Max: ${c.max_val ?? 'N/A'} · Mean: ${c.mean_val ?? 'N/A'}`,
      }));

      return {
        datasetName: `${datasetKey}.csv`,
        totalRows: data.total_rows || data.sample_size || 0,
        columnCount: data.columns_count || cols.length,
        completeness: Math.round(data.health_score || 95),
        failedRules: 0,
        columns: cols,
        controlResults: [],
        rules: [],
      };
    } catch (e) {
      console.warn('Failed to load dataset profile from database:', e);
      return {
        datasetName: `${datasetKey}.csv`,
        totalRows: 0,
        columnCount: 0,
        completeness: 100,
        failedRules: 0,
        columns: [],
        controlResults: [],
        rules: [],
      };
    }
  }
}

export const dataQualityDataSource: DataQualityDataSource = new LocalCsvDataQualityDataSource();
