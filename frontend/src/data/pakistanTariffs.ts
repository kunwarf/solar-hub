// Pakistani DISCO (Distribution Company) Tariff Data

export type DiscoCode = 
  | 'LESCO' | 'KELECTRIC' | 'MEPCO' | 'IESCO' | 'PESCO' 
  | 'FESCO' | 'HESCO' | 'QESCO' | 'GEPCO' | 'SEPCO';

export type ConsumerCategory = 'residential' | 'commercial' | 'industrial' | 'agricultural';
export type ResidentialSubcategory = 'protected' | 'unprotected';
export type ConnectionType = 'single_phase' | 'three_phase';

export interface TariffSlab {
  minUnits: number;
  maxUnits: number | null; // null means unlimited
  ratePerKwh: number;
}

export interface FixedCharges {
  singlePhase: number;
  threePhase: number;
}

export interface DiscoInfo {
  code: DiscoCode;
  name: string;
  fullName: string;
  region: string;
}

export interface TariffConfig {
  disco: DiscoCode;
  consumerCategory: ConsumerCategory;
  residentialSubcategory?: ResidentialSubcategory;
  connectionType: ConnectionType;
  sanctionedLoad: number; // kW
  netMeteringEnabled: boolean;
  fuelPriceAdjustment: number; // Rs/kWh (editable monthly)
  quarterlyTariffAdjustment: number; // Rs/kWh
}

export interface BillBreakdown {
  unitsConsumed: number;
  unitsExported: number;
  netUnits: number;
  
  // Slab-wise breakdown
  slabBreakdown: Array<{
    slab: TariffSlab;
    units: number;
    amount: number;
  }>;
  
  // Base charges
  energyCharges: number;
  fixedCharges: number;
  fuelPriceAdjustment: number;
  quarterlyTariffAdjustment: number;
  
  // Duties and taxes
  electricityDuty: number;
  gst: number;
  tvFee: number;
  
  // Net metering
  exportCredits: number;
  
  // Totals
  subtotal: number;
  totalAmount: number;
}

// All Pakistani DISCOs
export const DISCO_LIST: DiscoInfo[] = [
  { code: 'LESCO', name: 'LESCO', fullName: 'Lahore Electric Supply Company', region: 'Lahore, Kasur, Sheikhupura, Okara' },
  { code: 'KELECTRIC', name: 'K-Electric', fullName: 'K-Electric Limited', region: 'Karachi' },
  { code: 'MEPCO', name: 'MEPCO', fullName: 'Multan Electric Power Company', region: 'Multan, Sahiwal, Bahawalpur, DG Khan' },
  { code: 'IESCO', name: 'IESCO', fullName: 'Islamabad Electric Supply Company', region: 'Islamabad, Rawalpindi, Attock' },
  { code: 'PESCO', name: 'PESCO', fullName: 'Peshawar Electric Supply Company', region: 'Peshawar, Mardan, Swat' },
  { code: 'FESCO', name: 'FESCO', fullName: 'Faisalabad Electric Supply Company', region: 'Faisalabad, Jhang, Sargodha' },
  { code: 'HESCO', name: 'HESCO', fullName: 'Hyderabad Electric Supply Company', region: 'Hyderabad, Mirpurkhas' },
  { code: 'QESCO', name: 'QESCO', fullName: 'Quetta Electric Supply Company', region: 'Quetta, Balochistan' },
  { code: 'GEPCO', name: 'GEPCO', fullName: 'Gujranwala Electric Power Company', region: 'Gujranwala, Sialkot, Gujrat' },
  { code: 'SEPCO', name: 'SEPCO', fullName: 'Sukkur Electric Power Company', region: 'Sukkur, Larkana' },
];

// Residential Protected Consumer Tariff Slabs (NEPRA Approved)
export const RESIDENTIAL_PROTECTED_SLABS: TariffSlab[] = [
  { minUnits: 1, maxUnits: 100, ratePerKwh: 7.74 },
  { minUnits: 101, maxUnits: 200, ratePerKwh: 10.06 },
  { minUnits: 201, maxUnits: 300, ratePerKwh: 14.82 },
  { minUnits: 301, maxUnits: 700, ratePerKwh: 24.40 },
  { minUnits: 701, maxUnits: null, ratePerKwh: 30.72 },
];

// Residential Unprotected Consumer Tariff Slabs
export const RESIDENTIAL_UNPROTECTED_SLABS: TariffSlab[] = [
  { minUnits: 1, maxUnits: 100, ratePerKwh: 19.42 },
  { minUnits: 101, maxUnits: 200, ratePerKwh: 22.35 },
  { minUnits: 201, maxUnits: 300, ratePerKwh: 25.10 },
  { minUnits: 301, maxUnits: 700, ratePerKwh: 29.78 },
  { minUnits: 701, maxUnits: null, ratePerKwh: 35.24 },
];

// Commercial Tariff (flat rate based on time of use)
export const COMMERCIAL_RATE = 31.56; // Rs/kWh average

// Industrial Tariff Slabs (based on load)
export const INDUSTRIAL_SLABS: TariffSlab[] = [
  { minUnits: 1, maxUnits: 50000, ratePerKwh: 24.80 },
  { minUnits: 50001, maxUnits: 500000, ratePerKwh: 22.15 },
  { minUnits: 500001, maxUnits: null, ratePerKwh: 20.50 },
];

// Agricultural Tariff (Tube Well)
export const AGRICULTURAL_RATE = 14.28; // Rs/kWh (subsidized)

// Fixed Charges (Monthly)
export const FIXED_CHARGES: Record<ConsumerCategory, FixedCharges> = {
  residential: { singlePhase: 75, threePhase: 150 },
  commercial: { singlePhase: 350, threePhase: 500 },
  industrial: { singlePhase: 500, threePhase: 1000 },
  agricultural: { singlePhase: 50, threePhase: 100 },
};

// Additional Charges
export const ELECTRICITY_DUTY_RATE = 0.015; // 1.5%
export const GST_RATE = 0.17; // 17%
export const GST_THRESHOLD = 25000; // Only applicable above this amount
export const TV_FEE = 35; // Rs flat
export const NET_METERING_EXPORT_RATE = 19.32; // Rs/kWh (NEPRA approved)

// Default FPA and QTA values (these change monthly/quarterly)
export const DEFAULT_FPA = 3.23; // Rs/kWh (Fuel Price Adjustment)
export const DEFAULT_QTA = 1.45; // Rs/kWh (Quarterly Tariff Adjustment)

// Consumer Category Labels
export const CONSUMER_CATEGORY_LABELS: Record<ConsumerCategory, string> = {
  residential: 'Residential',
  commercial: 'Commercial',
  industrial: 'Industrial',
  agricultural: 'Agricultural (Tube Well)',
};

export const RESIDENTIAL_SUBCATEGORY_LABELS: Record<ResidentialSubcategory, string> = {
  protected: 'Protected (Low Usage)',
  unprotected: 'Unprotected (Regular)',
};

export const CONNECTION_TYPE_LABELS: Record<ConnectionType, string> = {
  single_phase: 'Single Phase',
  three_phase: 'Three Phase',
};

// Get tariff slabs based on consumer category
export const getTariffSlabs = (
  category: ConsumerCategory,
  subcategory?: ResidentialSubcategory
): TariffSlab[] | number => {
  switch (category) {
    case 'residential':
      return subcategory === 'protected' 
        ? RESIDENTIAL_PROTECTED_SLABS 
        : RESIDENTIAL_UNPROTECTED_SLABS;
    case 'commercial':
      return COMMERCIAL_RATE;
    case 'industrial':
      return INDUSTRIAL_SLABS;
    case 'agricultural':
      return AGRICULTURAL_RATE;
    default:
      return RESIDENTIAL_PROTECTED_SLABS;
  }
};

// Calculate energy charges based on slabs
export const calculateSlabCharges = (
  units: number,
  slabs: TariffSlab[]
): { breakdown: Array<{ slab: TariffSlab; units: number; amount: number }>; total: number } => {
  const breakdown: Array<{ slab: TariffSlab; units: number; amount: number }> = [];
  let remainingUnits = units;
  let total = 0;

  for (const slab of slabs) {
    if (remainingUnits <= 0) break;

    const slabMax = slab.maxUnits ?? Infinity;
    const slabRange = slabMax - slab.minUnits + 1;
    const unitsInSlab = Math.min(remainingUnits, slabRange);
    const amount = unitsInSlab * slab.ratePerKwh;

    breakdown.push({ slab, units: unitsInSlab, amount });
    total += amount;
    remainingUnits -= unitsInSlab;
  }

  return { breakdown, total };
};

// Calculate complete bill
export const calculateBill = (
  unitsConsumed: number,
  unitsExported: number,
  config: TariffConfig
): BillBreakdown => {
  // Get tariff slabs or flat rate
  const tariff = getTariffSlabs(config.consumerCategory, config.residentialSubcategory);
  
  // Calculate energy charges
  let energyCharges = 0;
  let slabBreakdown: Array<{ slab: TariffSlab; units: number; amount: number }> = [];
  
  if (typeof tariff === 'number') {
    // Flat rate
    energyCharges = unitsConsumed * tariff;
    slabBreakdown = [{
      slab: { minUnits: 1, maxUnits: null, ratePerKwh: tariff },
      units: unitsConsumed,
      amount: energyCharges,
    }];
  } else {
    // Slab-based
    const result = calculateSlabCharges(unitsConsumed, tariff);
    energyCharges = result.total;
    slabBreakdown = result.breakdown;
  }

  // Fixed charges
  const fixedChargesConfig = FIXED_CHARGES[config.consumerCategory];
  const fixedCharges = config.connectionType === 'single_phase' 
    ? fixedChargesConfig.singlePhase 
    : fixedChargesConfig.threePhase;

  // FPA and QTA
  const fuelPriceAdjustment = unitsConsumed * config.fuelPriceAdjustment;
  const quarterlyTariffAdjustment = unitsConsumed * config.quarterlyTariffAdjustment;

  // Subtotal before taxes
  const subtotal = energyCharges + fixedCharges + fuelPriceAdjustment + quarterlyTariffAdjustment;

  // Electricity Duty (1.5%)
  const electricityDuty = subtotal * ELECTRICITY_DUTY_RATE;

  // GST (17% on amounts > Rs. 25,000)
  const amountForGst = subtotal + electricityDuty;
  const gst = amountForGst > GST_THRESHOLD ? amountForGst * GST_RATE : 0;

  // TV Fee
  const tvFee = TV_FEE;

  // Net metering export credits
  const exportCredits = config.netMeteringEnabled 
    ? unitsExported * NET_METERING_EXPORT_RATE 
    : 0;

  // Net units after export
  const netUnits = Math.max(0, unitsConsumed - unitsExported);

  // Total amount
  const totalAmount = subtotal + electricityDuty + gst + tvFee - exportCredits;

  return {
    unitsConsumed,
    unitsExported,
    netUnits,
    slabBreakdown,
    energyCharges,
    fixedCharges,
    fuelPriceAdjustment,
    quarterlyTariffAdjustment,
    electricityDuty,
    gst,
    tvFee,
    exportCredits,
    subtotal,
    totalAmount: Math.max(0, totalAmount),
  };
};

// Default tariff config
export const getDefaultTariffConfig = (): TariffConfig => ({
  disco: 'LESCO',
  consumerCategory: 'residential',
  residentialSubcategory: 'protected',
  connectionType: 'single_phase',
  sanctionedLoad: 5,
  netMeteringEnabled: true,
  fuelPriceAdjustment: DEFAULT_FPA,
  quarterlyTariffAdjustment: DEFAULT_QTA,
});
