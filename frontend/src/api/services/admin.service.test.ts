import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { providersService, tariffsService } from './admin.service';
import apiClient from '../client';
import type { ElectricityProvider, TariffPlan } from '@/types/admin';

// Mock the API client
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Admin Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('providersService', () => {
    it('should list providers', async () => {
      const mockProviders: ElectricityProvider[] = [
        {
          id: 'p1',
          name: 'LESCO',
          shortName: 'LESCO',
          region: 'Punjab',
          status: 'active',
          tariffCount: 5,
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: '2024-01-01T00:00:00Z',
        },
      ];

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockProviders });

      const result = await providersService.list();

      expect(apiClient.get).toHaveBeenCalledWith('/admin/providers');
      expect(result).toEqual(mockProviders);
    });

    it('should get provider by id', async () => {
      const mockProvider: ElectricityProvider = {
        id: 'p1',
        name: 'LESCO',
        shortName: 'LESCO',
        region: 'Punjab',
        status: 'active',
        tariffCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
      };

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockProvider });

      const result = await providersService.getById('p1');

      expect(apiClient.get).toHaveBeenCalledWith('/admin/providers/p1');
      expect(result).toEqual(mockProvider);
    });

    it('should create provider', async () => {
      const newProvider = {
        name: 'GEPCO',
        shortName: 'GEPCO',
        region: 'Punjab',
        status: 'active' as const,
      };

      const createdProvider: ElectricityProvider = {
        id: 'p2',
        ...newProvider,
        tariffCount: 0,
        createdAt: '2024-01-02T00:00:00Z',
        updatedAt: '2024-01-02T00:00:00Z',
      };

      vi.mocked(apiClient.post).mockResolvedValue({ data: createdProvider });

      const result = await providersService.create(newProvider);

      expect(apiClient.post).toHaveBeenCalledWith('/admin/providers', newProvider);
      expect(result).toEqual(createdProvider);
    });

    it('should update provider', async () => {
      const updateData = { status: 'inactive' as const };
      const updatedProvider: ElectricityProvider = {
        id: 'p1',
        name: 'LESCO',
        shortName: 'LESCO',
        region: 'Punjab',
        status: 'inactive',
        tariffCount: 5,
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-02T00:00:00Z',
      };

      vi.mocked(apiClient.put).mockResolvedValue({ data: updatedProvider });

      const result = await providersService.update('p1', updateData);

      expect(apiClient.put).toHaveBeenCalledWith('/admin/providers/p1', updateData);
      expect(result).toEqual(updatedProvider);
    });

    it('should delete provider', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });

      await providersService.delete('p1');

      expect(apiClient.delete).toHaveBeenCalledWith('/admin/providers/p1');
    });

    it('should handle API errors', async () => {
      const error = { message: 'Network error' };
      vi.mocked(apiClient.get).mockRejectedValue(error);

      await expect(providersService.list()).rejects.toEqual(error);
    });
  });

  describe('tariffsService', () => {
    it('should list tariffs', async () => {
      const mockTariffs: TariffPlan[] = [
        {
          id: 't1',
          providerId: 'p1',
          name: 'Residential Unprotected',
          category: 'residential',
          type: 'slab',
          rates: {
            slabs: [
              { minUnits: 0, maxUnits: 100, ratePerKwh: 7.74 },
            ],
          },
          fixedCharges: 150,
          effectiveFrom: '2024-01-01',
          effectiveTo: null,
          status: 'active',
        },
      ];

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockTariffs });

      const result = await tariffsService.list();

      expect(apiClient.get).toHaveBeenCalledWith('/admin/tariffs', { params: undefined });
      expect(result).toEqual(mockTariffs);
    });

    it('should list tariffs with provider filter', async () => {
      const mockTariffs: TariffPlan[] = [];

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockTariffs });

      await tariffsService.list({ providerId: 'p1' });

      expect(apiClient.get).toHaveBeenCalledWith('/admin/tariffs', {
        params: { providerId: 'p1' },
      });
    });

    it('should create tariff', async () => {
      const newTariff = {
        providerId: 'p1',
        name: 'New Tariff',
        category: 'residential' as const,
        type: 'slab' as const,
        rates: {
          slabs: [
            { minUnits: 0, maxUnits: 100, ratePerKwh: 7.74 },
          ],
        },
        fixedCharges: 150,
        effectiveFrom: '2024-01-01',
        effectiveTo: null,
        status: 'active' as const,
      };

      const createdTariff: TariffPlan = {
        id: 't2',
        ...newTariff,
      };

      vi.mocked(apiClient.post).mockResolvedValue({ data: createdTariff });

      const result = await tariffsService.create(newTariff);

      expect(apiClient.post).toHaveBeenCalledWith('/admin/tariffs', newTariff);
      expect(result).toEqual(createdTariff);
    });

    it('should update tariff', async () => {
      const updateData = { status: 'inactive' as const };
      const updatedTariff: TariffPlan = {
        id: 't1',
        providerId: 'p1',
        name: 'Residential Unprotected',
        category: 'residential',
        type: 'slab',
        rates: {
          slabs: [
            { minUnits: 0, maxUnits: 100, ratePerKwh: 7.74 },
          ],
        },
        fixedCharges: 150,
        effectiveFrom: '2024-01-01',
        effectiveTo: null,
        status: 'inactive',
      };

      vi.mocked(apiClient.put).mockResolvedValue({ data: updatedTariff });

      const result = await tariffsService.update('t1', updateData);

      expect(apiClient.put).toHaveBeenCalledWith('/admin/tariffs/t1', updateData);
      expect(result).toEqual(updatedTariff);
    });

    it('should delete tariff', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });

      await tariffsService.delete('t1');

      expect(apiClient.delete).toHaveBeenCalledWith('/admin/tariffs/t1');
    });
  });
});
